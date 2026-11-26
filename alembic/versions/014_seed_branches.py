"""Seed branch companies

Revision ID: 014_seed_branches
Revises: 013_hq_selfref
Create Date: 2025-11-07

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '014_seed_branches'
down_revision = '013_hq_selfref'
branch_labels = None
depends_on = None

BRANCH_NAMES = [
    "본사직영",
    "종로",
    "동대문/성동/광진",
    "동대문구",
    "노원중랑성북강북",
    "노원",
    "중랑",
    "강북구",
    "은평/서대문",
    "마포/용산",
    "마포용산",
    "금천",
    "영등포",
    "송파/강동",
    "송파",
    "강동",
    "부산",
    "부산 서구",
    "부산동구",
    "대구",
    "대구 서부",
    "인천",
    "부평",
    "광주, 전남서부",
    "광주",
    "대전",
    "대전 김선숙",
    "울산",
    "수원",
    "성남광주",
    "고양/파주",
    "용인/이천",
    "용인",
    "부천",
    "안양과천의왕군포",
    "안양",
    "화성",
    "평택/오산",
    "의정부/양주",
    "경기도 시흥",
    "시흥/광명",
    "시흥",
    "김포",
    "하남",
    "양주",
    "구리/남양주",
    "안성/평택",
    "안성",
    "의왕",
    "안산",
    "춘천",
    "원주",
    "강릉",
    "충북(청주제외)",
    "충주",
    "충북",
    "청주/세종",
    "청주세종",
    "진천",
    "충북 음성",
    "충남, 천안, 아산",
    "충남",
    "천안",
    "전북",
    "전주",
    "익산",
    "여수/순천/광양",
    "순천",
    "포항",
    "영천/경주",
    "구미/김천",
    "구미",
    "경산",
    "창원",
    "경남 진주",
    "통영거제",
    "경남 사천",
    "김해/양산",
    "밀양",
    "제주 임선지",
    "제주",
    "고성",
    "대구서부",
    "목포",
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if 'companies' not in tables:
        return
    cols = {c['name'] for c in inspector.get_columns('companies')}
    # Require company_type
    if 'company_type' not in cols:
        return
    # Find HQ company (first HQ or create one if none)
    hq_company_id = None
    try:
        res = conn.execute(sa.text("SELECT company_id FROM companies WHERE company_type='HQ' ORDER BY company_id LIMIT 1"))
        row = res.first()
        if row:
            hq_company_id = row[0]
    except Exception:
        pass
    if hq_company_id is None:
        # create default HQ
        try:
            conn.execute(sa.text("INSERT INTO companies (company_type, name, is_active) VALUES ('HQ', '본사', 1)"))
            res = conn.execute(sa.text("SELECT company_id FROM companies WHERE company_type='HQ' ORDER BY company_id LIMIT 1"))
            row = res.first()
            if row:
                hq_company_id = row[0]
        except Exception:
            return

    # Insert branches if not existing by name
    for name in BRANCH_NAMES:
        try:
            exists = conn.execute(sa.text("SELECT 1 FROM companies WHERE name=:n"), {"n": name}).first()
            if exists:
                continue
            conn.execute(sa.text("INSERT INTO companies (company_type, hq_company_id, name, is_active) VALUES ('BRANCH', :hq, :n, 1)"), {"hq": hq_company_id, "n": name})
        except Exception:
            # continue on error to keep idempotent behavior
            pass


def downgrade() -> None:
    conn = op.get_bind()
    # Remove only the seeded branches (exact name match) leaving any other companies intact
    for name in BRANCH_NAMES:
        try:
            conn.execute(sa.text("DELETE FROM companies WHERE company_type='BRANCH' AND name=:n"), {"n": name})
        except Exception:
            pass
