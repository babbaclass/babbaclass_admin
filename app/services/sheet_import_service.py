import csv
import io
import re
import urllib.parse
import requests
import logging
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

logger = logging.getLogger(__name__)


def normalize_table_name(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "sheet_table"


def normalize_column_name_keep_unicode(name: str) -> str:
    """Return a MySQL-safe column name preserving original (Unicode) characters.

    We only strip whitespace and replace backticks to avoid breaking identifier quoting.
    Empty names fall back to 'col'. Duplicates handled separately.
    MySQL supports Unicode in identifiers when quoted with backticks.
    """
    if name is None:
        return "col"
    s = name.strip().replace("`", "_")
    if not s:
        s = "col"
    return s


def infer_type(values: List[str]) -> str:
    """Infer MySQL column type from sample values.
    Returns MySQL type string (e.g., INT, DOUBLE, BOOLEAN, DATETIME, VARCHAR(255))
    """
    non_empty = [v for v in values if v not in (None, "", "null", "NULL")]
    if not non_empty:
        return "VARCHAR(255)"

    def is_int(v: str) -> bool:
        try:
            int(v)
            return True
        except Exception:
            return False

    def is_float(v: str) -> bool:
        try:
            float(v)
            return True
        except Exception:
            return False

    def is_bool(v: str) -> bool:
        return v.strip().lower() in {"true", "false", "1", "0", "y", "n", "yes", "no"}

    def is_datetime_like(v: str) -> bool:
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?$", v.strip()))

    if all(is_int(v) for v in non_empty):
        return "INT"
    if all(is_float(v) for v in non_empty):
        return "DOUBLE"
    if all(is_bool(v) for v in non_empty):
        return "BOOLEAN"
    if all(is_datetime_like(v) for v in non_empty):
        return "DATETIME"

    # default to VARCHAR with length based on max value
    max_len = max(len(v) for v in non_empty)
    if max_len <= 255:
        return "VARCHAR(255)"
    elif max_len <= 1000:
        return "VARCHAR(1000)"
    else:
        return "TEXT"


def google_sheet_to_csv_url(sheet_url: str, sheet_name: str | None = None) -> str:
    """Convert various Google Sheets URLs into a direct CSV export URL.

    Supports:
    - https://docs.google.com/spreadsheets/d/<ID>/edit?gid=<GID>
    - https://docs.google.com/spreadsheets/d/<ID>/edit#gid=<GID>
    - https://docs.google.com/spreadsheets/d/<ID>/... (first sheet)
    - Optional sheet_name fallback via gviz
    """
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not m:
        # Assume already CSV direct link
        return sheet_url
    spreadsheet_id = m.group(1)

    # Parse query and fragment for gid
    parsed = urllib.parse.urlparse(sheet_url)
    q = urllib.parse.parse_qs(parsed.query)
    gid = None
    if "gid" in q and q["gid"]:
        gid = q["gid"][0]
    else:
        # Sometimes gid is in fragment '#gid=12345'
        if parsed.fragment and parsed.fragment.startswith("gid="):
            gid = parsed.fragment.split("=", 1)[1]

    if gid:
        # Reliable CSV export for a specific sheet by gid
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"

    # No gid: either use a named sheet via gviz or default (first sheet) export
    if sheet_name:
        return (
            f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet="
            f"{urllib.parse.quote(sheet_name)}"
        )
    # Default to first sheet CSV export
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"


def fetch_csv(sheet_url: str) -> str:
    r = requests.get(sheet_url, timeout=20)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        status = r.status_code
        if status == 403:
            raise ValueError("Google Sheet 접근이 거부되었습니다(403). 시트 공유 설정을 '링크가 있는 모든 사용자'로 변경하세요.") from e
        if status == 404:
            raise ValueError("Google Sheet을 찾을 수 없습니다(404). URL의 ID/gid가 올바른지 확인하세요.") from e
        raise
    # Force UTF-8 with BOM handling to avoid Korean text corruption
    return r.content.decode("utf-8-sig", errors="strict")


def parse_csv(text_data: str) -> Tuple[List[str], List[List[str]]]:
    """Parse CSV preserving original (Unicode) headers.

    Returns:
        headers: possibly de-duplicated safe headers (original Unicode retained).
        data: remaining rows.
    """
    reader = csv.reader(io.StringIO(text_data))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV 데이터가 비었습니다.")
    raw_headers = rows[0]
    data = rows[1:]
    # Sanitize & preserve unicode
    sanitized = [normalize_column_name_keep_unicode(h) for h in raw_headers]
    seen: Dict[str, int] = {}
    final_headers: List[str] = []
    for h in sanitized:
        if h not in seen:
            seen[h] = 0
            final_headers.append(h)
        else:
            seen[h] += 1
            final_headers.append(f"{h}_{seen[h]}")
    return final_headers, data


def ensure_table(db: Session, table_name: str, headers: List[str], data: List[List[str]]):
    # Determine types from first up to 100 rows
    sample_cols = list(zip(*data[:100])) if data else [[] for _ in headers]
    types = [infer_type(list(col)) for col in sample_cols]

    engine = db.get_bind()
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if table_name not in existing_tables:
        cols_sql = ", ".join(f"`{h}` {t} NULL" for h, t in zip(headers, types))
        sql = f"CREATE TABLE `{table_name}` (id INT AUTO_INCREMENT PRIMARY KEY, {cols_sql}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
        db.execute(text(sql))
        return True, types
    else:
        # Ensure missing columns are added
        existing_cols = {col['name'] for col in inspector.get_columns(table_name)}
        for h, t in zip(headers, types):
            if h not in existing_cols:
                db.execute(text(f"ALTER TABLE `{table_name}` ADD COLUMN `{h}` {t} NULL"))
        return False, types


def insert_rows(db: Session, table_name: str, headers: List[str], data: List[List[str]], truncate_before: bool = False) -> int:
    """Bulk insert using safe parameter names to support any header characters.

    We keep column names as-is (quoted with backticks), but bind parameters use
    generated names p0, p1, ... to avoid illegal identifier issues.
    """
    if truncate_before:
        db.execute(text(f"TRUNCATE TABLE `{table_name}`"))
    if not data:
        return 0

    param_names = [f"p{i}" for i in range(len(headers))]
    placeholders = ", ".join(f":{p}" for p in param_names)
    columns_sql = ", ".join(f"`{h}`" for h in headers)
    insert_sql = text(f"INSERT INTO `{table_name}` ({columns_sql}) VALUES ({placeholders})")

    rows = []
    for row in data:
        d = {}
        for i, p in enumerate(param_names):
            v = row[i] if i < len(row) else None
            if v in ("", "null", "NULL"):
                v = None
            d[p] = v
        rows.append(d)

    db.execute(insert_sql, rows)
    return len(rows)


RESERVED_TABLES = {"user", "users", "company", "companies", "order", "orders", "product", "products"}
ALLOWED_PREFIX = "sheet_"


def safe_table_name(raw: str) -> str:
    n = normalize_table_name(raw)
    if not n.startswith(ALLOWED_PREFIX):
        n = f"{ALLOWED_PREFIX}{n}"
    if n in RESERVED_TABLES:
        n = f"{n}_data"
    return n


def import_google_sheet(db: Session, sheet_url: str, sheet_name: str | None = None, table_name: str | None = None, truncate_before: bool = False) -> Dict[str, Any]:
    tn = safe_table_name(table_name or (sheet_name or "google_sheet"))
    logger.info(f"[SheetImport] Start import: url={sheet_url}, sheet={sheet_name}, table={tn}, truncate_before={truncate_before}")
    csv_url = google_sheet_to_csv_url(sheet_url, sheet_name)
    csv_text = fetch_csv(csv_url)
    headers, data = parse_csv(csv_text)
    logger.info(f"[SheetImport] Parsed CSV: columns={len(headers)}, rows={len(data)} -> headers={headers}")
    created, types = ensure_table(db, tn, headers, data)
    logger.info(f"[SheetImport] Ensure table: name={tn}, created={created}, columns={types}")
    inserted = insert_rows(db, tn, headers, data, truncate_before=truncate_before)
    db.commit()
    logger.info(f"[SheetImport] Inserted rows: count={inserted} into {tn}")
    return {
        "status": "ok",
        "table_name": tn,
        "created_table": created,
        "columns": {h: t for h, t in zip(headers, types)},
        "rows_inserted": inserted,
        "csv_url": csv_url,
    }
