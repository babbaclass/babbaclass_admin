from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse
import traceback
import os
import json
from pydantic import BaseModel
from google.cloud import tasks_v2
from app.database import Base, engine, get_db
from app.models import User, Product, Order, OrderItem, Member
from app.admin import setup_admin
from app.middleware.admin_sidebar import AdminSidebarMiddleware
from app.services.makeshop_service import MakeshopAPIError
from app.services.makeshop_api_gateway import (
    fetch_members_page,
    fetch_orders_page,
    fetch_products_page,
    health_check as makeshop_health_check,
    use_makeshop_rest,
)
from app.services.makeshop_sync_service import (
    iter_inquiry_day_windows,
    resolve_order_sync_window,
    should_fetch_next_order_page,
)
from app.routers import organization
from app.routers import admin_bootstrap
from app.routers import admin_sheet_import
from app.routers import admin_settlement_api
from app.routers import admin_views
from app.routers import admin_security
from app.routers import batch
from app.routers import makeshop
from app.routes.settlement_statement import router as settlement_statement_router
import logging

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID") or "astute-window-472313-g9"
TASKS_QUEUE_NAME = os.getenv("TASKS_QUEUE_NAME", "makeshop-sync-queue")
TASKS_QUEUE_LOCATION = os.getenv("TASKS_QUEUE_LOCATION", "asia-northeast3")
TASKS_BACKGROUND_PATH = os.getenv("TASKS_BACKGROUND_PATH", "/tasks/sync/makeshop/run")
TASKS_SERVICE_ACCOUNT = os.getenv("TASKS_SERVICE_ACCOUNT")

def parse_quantity(value):
    """
    API 응답의 quantity 값을 파싱합니다.
    - 'Unlimited' 문자열 → -1로 변환
    - 숫자는 정수로 변환
    - 그 외 → 0으로 기본값 설정
    """
    if isinstance(value, str):
        if value.lower() == 'unlimited':
            return -1
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    elif isinstance(value, int):
        return value
    else:
        return 0


def safe_string(value):
    """API 데이터를 안전하게 문자열로 변환"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value)
    if isinstance(value, (list, tuple)):
        return str(value)
    return str(value)


def safe_int(value):
    """API 데이터를 안전하게 정수로 변환"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return None


class TrustProtoMiddleware(BaseHTTPMiddleware):
    """Middleware to trust X-Forwarded-* headers from Cloud Run proxy
    This ensures SQLAdmin generates correct absolute URLs for static assets
    
    Cloud Run passes:
    - X-Forwarded-Proto: https
    - X-Forwarded-Host: example.run.app
    - X-Forwarded-For: client-ip
    """
    async def dispatch(self, request, call_next):
        # Trust proxy headers from Cloud Run (only for HTTPS/domain info, not response manipulation)
        if request.headers.get("X-Forwarded-Proto"):
            request.scope["scheme"] = request.headers.get("X-Forwarded-Proto")
        
        if request.headers.get("X-Forwarded-Host"):
            host = request.headers.get("X-Forwarded-Host")
            # Extract just the hostname without port
            host_only = host.split(":")[0] if ":" in host else host
            # Keep existing port from scope if available, or use default based on scheme
            existing_port = request.scope.get("server", ("localhost", 80))[1]
            request.scope["server"] = (host_only, existing_port)
        
        response = await call_next(request)
        return response


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """Logs unhandled exceptions with full traceback, then re-raises to preserve default handlers."""
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Unhandled error: {e}\nPath: {request.method} {request.url}\nHeaders: {dict(request.headers)}\nTraceback:\n{tb}")
            # Re-raise to keep FastAPI/Starlette default error handling (HTML/JSON as appropriate)
            raise


class ExportEncodingMiddleware(BaseHTTPMiddleware):
    """Fix export encoding for CSV/JSON downloads to support Korean characters"""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Check if this is an export request (CSV or JSON download)
        if "export" in request.url.path or request.url.path.endswith((".csv", ".json")):
            content_type = response.headers.get("content-type", "")
            if "text/csv" in content_type or "application/json" in content_type:
                # Set UTF-8 charset explicitly
                if "charset" not in content_type:
                    response.headers["content-type"] = f"{content_type}; charset=utf-8"
        
        return response


class AdminIndexRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect /admin/ to role-specific pages after login"""
    async def dispatch(self, request, call_next):
        from starlette.responses import RedirectResponse
        
        # /admin/ 또는 /admin 경로 요청 시 role_id에 따라 리다이렉트
        if request.url.path in ["/admin/", "/admin"]:
            # 세션이 존재하는지 안전하게 확인
            if "session" in request.scope:
                session = request.scope["session"]
                role_id = session.get("role_id")
                logger.info(f"[AdminIndexRedirect] path={request.url.path}, session={session}, role_id={role_id}")
                
                if role_id == 2:
                    # 지사장: 정산 개요로 리다이렉트
                    logger.info("[AdminIndexRedirect] Redirecting role_id=2 to settlement-overview")
                    return RedirectResponse(url="/admin/settlement-overview", status_code=302)
                elif role_id == 1:
                    # 관리자: 홈 대시보드로 리다이렉트
                    logger.info("[AdminIndexRedirect] Redirecting role_id=1 to home dashboard")
                    return RedirectResponse(url="/admin/home", status_code=302)
            else:
                logger.info(f"[AdminIndexRedirect] No session in scope for path={request.url.path}")
        
        return await call_next(request)


app = FastAPI(
    title="babba-api",
    description="FastAPI on Google Cloud Run with Cloud SQL",
    version="1.0.0"
)

# Add middleware to trust proxy headers for Cloud Run
app.add_middleware(TrustProtoMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
# AdminSidebarMiddleware 비활성화 - role 기반 visibility는 admin.py에서 처리
# app.add_middleware(AdminSidebarMiddleware)

# AdminIndexRedirectMiddleware는 SessionMiddleware 이후에 실행되어야 하므로 
# setup_admin() 전에 추가 (미들웨어는 역순 실행)
app.add_middleware(AdminIndexRedirectMiddleware)

# Include organization routers FIRST (before SQLAdmin setup)
app.include_router(organization.router)
app.include_router(admin_bootstrap.router)
app.include_router(admin_sheet_import.router)
app.include_router(admin_views.router)  # Admin 뷰 라우터 (Commission, Data Tools)
app.include_router(admin_settlement_api.router, prefix="/api/admin")  # 정산 API 라우터 (AJAX용, prefix 추가하여 프런트엔드 fetch 경로와 일치)
app.include_router(admin_security.router, prefix="/api/admin")
app.include_router(makeshop.router, prefix="/api")  # 메이크샵 API 라우터 (/api/makeshop/*)
# MakeShop 개발자센터 APP URL: https://<host>/makeshop/install
# Docs: https://developer.makeshop.co.kr/docs/guide/app/install
app.add_api_route(
    "/makeshop/install",
    makeshop.makeshop_install,
    methods=["GET"],
    tags=["Makeshop"],
)
app.include_router(batch.router)  # 배치 작업 라우터 (Cloud Scheduler 연동)
app.include_router(settlement_statement_router, prefix="/admin")

# Setup SQLAdmin with /admin base_url
# (정적 파일 마운트는 setup_admin 함수 내에서 처리됨)
# SessionMiddleware는 setup_admin 내에서 추가됨
setup_admin(app)

# Removed custom user create router (simplified contacts removal)

@app.on_event("startup")
async def startup_event():
    """Startup hook (migrations handled by CI/CD)."""
    import os
    from sqlalchemy import text, inspect
    
    try:
        logger.info("🚀 Starting application initialization...")
        
        # Avoid auto-creating tables in production; enable only if explicitly requested.
        if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully (AUTO_CREATE_TABLES=true)")
        
        # Role initialization: ensure required roles exist (safe, idempotent approach)
        required_roles = {
            "본사 관리자": "본사 관리 역할",
            "지사장": "지점 운영 역할",
            "원장": "학원 운영 역할"
        }
        with engine.begin() as conn:
            try:
                # Check if roles table is empty or corrupted
                role_count_result = conn.execute(text("SELECT COUNT(*) FROM roles")).scalar()
                role_count = role_count_result or 0
                
                if role_count > 0:
                    existing_roles = conn.execute(text("SELECT role_name FROM roles")).fetchall()
                    existing_role_names = {str(r[0]) for r in existing_roles}
                else:
                    existing_role_names = set()
                
                # Only insert missing required roles (don't delete existing ones)
                missing_roles = [name for name in required_roles.keys() if name not in existing_role_names]
                
                if missing_roles:
                    logger.info(f"Inserting missing roles: {missing_roles}")
                    for role_name in missing_roles:
                        try:
                            conn.execute(text(
                                "INSERT INTO roles (role_name, description, is_active) VALUES (:name, :desc, 1)"
                            ), {"name": role_name, "desc": required_roles[role_name]})
                        except Exception as insert_ex:
                            # Handle duplicate key error gracefully
                            if "Duplicate" not in str(insert_ex):
                                logger.warning(f"Could not insert role {role_name}: {insert_ex}")
                    logger.info("✓ Required roles ensured successfully")
                else:
                    logger.info("✓ All required roles already exist")
                    
            except Exception as ex:
                logger.warning(f"⚠️ Role initialization encountered issues (continuing anyway): {ex}")

        # Ensure users.code column exists (safety net if Alembic migration not yet applied)
        try:
            with engine.begin() as conn2:
                ins = inspect(conn2)
                tables = set(ins.get_table_names())
                if 'users' in tables:
                    cols = {c['name'] for c in ins.get_columns('users')}
                    if 'code' not in cols:
                        conn2.execute(text("ALTER TABLE users ADD COLUMN code INT NULL"))
                        logger.info("✓ Added users.code column")
                        # Create index if not exists
                        try:
                            idx_names = {i.get('name') for i in ins.get_indexes('users')}
                            if 'ix_users_code' not in idx_names:
                                conn2.execute(text("CREATE INDEX ix_users_code ON users (code)"))
                                logger.info("✓ Created index on users.code")
                        except Exception:
                            pass
        except Exception as _e:
            logger.warning(f"⚠️ users.code column check failed (will rely on Alembic): {_e}")
        
        logger.info("✅ Application initialization completed")
    
    except Exception as e:
        logger.error(f"❌ Critical error during startup: {e}", exc_info=True)
        logger.warning("⚠️ Continuing with degraded startup - check logs for details")
@app.get("/", tags=["Health"])
def read_root():
    """Root endpoint - API is running"""
    return {
        "message": "babba-api is running",
        "version": "1.0.0",
        "admin_panel": "https://babba-api-1024083500192.asia-northeast3.run.app/admin/",
        "swagger_docs": "https://babba-api-1024083500192.asia-northeast3.run.app/docs"
    }

@app.get("/admin-info", tags=["Admin"])
def admin_info():
    """
    관리자 페이지 정보
    
    SQLAdmin 관리자 페이지에 접속하여 모든 데이터를 관리할 수 있습니다.
    
    실제 관리자 페이지는 /admin/ 경로에 있습니다.
    
    Features:
    - 모든 데이터베이스 테이블 조회 및 편집
    - 검색 및 필터링
    - 일괄 작업
    - 관리자 대시보드
    
    관리되는 모델:
    - 사용자 (User)
    - 회사 (Company)
    - 역할 (Role)
    - 카테고리 (Category)
    - 상품 (Product)
    - 주문 (Order)
    - 주문항목 (OrderItem)
    - 회원 (Member)
    """
    return {
        "message": "SQLAdmin 관리자 페이지",
        "url": "/admin/",
        "features": [
            "모든 데이터베이스 테이블 CRUD 작업",
            "고급 검색 및 필터링",
            "일괄 작업",
            "관리자 대시보드"
        ],
        "models": [
            "사용자 (User)",
            "회사 (Company)",
            "역할 (Role)",
            "카테고리 (Category)",
            "상품 (Product)",
            "주문 (Order)",
            "주문항목 (OrderItem)",
            "회원 (Member)"
        ],
        "sheet_tools": {
            "import_sheet": "/admin-api/sheets/import"
        }
    }

@app.get("/debug/routes", tags=["Debug"])
def list_routes():
    """List all loaded routes (paths and methods) to verify router inclusion in runtime."""
    routes = []
    for r in app.router.routes:  # type: ignore[attr-defined]
        try:
            routes.append({
                "path": getattr(r, "path", None),
                "name": getattr(r, "name", None),
                "methods": list(getattr(r, "methods", []) or []),
            })
        except Exception:
            continue
    return {"count": len(routes), "routes": routes}

@app.get("/version", tags=["Debug"])
def version_info():
    """Return app version and git SHA (if provided via env var GIT_SHA)."""
    import os
    return {
        "app": "babba-api",
        "version": "1.0.0",
        "git_sha": os.getenv("GIT_SHA"),
    }

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint - basic connectivity test"""
    return {"status": "healthy"}

@app.get("/health/db", tags=["Health"])
def health_check_with_db(db: Session = Depends(get_db)):
    """Health check endpoint with database connection test"""
    try:
        # Test database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/database/tables", tags=["Database"])
def get_database_tables():
    """Get all tables in Cloud SQL database"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        
        if not table_names:
            return {
                "status": "no_tables",
                "tables": [],
                "total": 0
            }
        
        tables_info = []
        
        with engine.connect() as connection:
            for table_name in sorted(table_names):
                columns = inspector.get_columns(table_name)
                pk_constraint = inspector.get_pk_constraint(table_name)
                pk_columns = set(pk_constraint.get('constrained_columns', []))
                
                # 각 테이블의 데이터 개수
                from sqlalchemy import text
                query = text(f"SELECT COUNT(*) as cnt FROM {table_name}")
                result = connection.execute(query)
                row_count = result.scalar()
                
                columns_info = []
                for col in columns:
                    columns_info.append({
                        "name": col['name'],
                        "type": str(col['type']),
                        "nullable": col['nullable'],
                        "is_primary_key": col['name'] in pk_columns
                    })
                
                tables_info.append({
                    "name": table_name,
                    "columns": columns_info,
                    "column_count": len(columns),
                    "row_count": row_count
                })
        
        return {
            "status": "success",
            "tables": tables_info,
            "total": len(tables_info)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# (Legacy user endpoints removed — consolidated under /api/v1/users in organization router.)


# ============================================================================
# Legacy Endpoints (For backward compatibility)
# ============================================================================

@app.get("/items/{item_id}", tags=["Legacy"])
def read_item(item_id: int, q: Optional[str] = None):
    """Legacy endpoint - items lookup"""
    return {"item_id": item_id, "q": q}


# ============================================================================
# Makeshop Integration Endpoints (Sync)
# ============================================================================

def _run_makeshop_sync(
    db: Session,
    InquiryTimeFrom: Optional[str] = None,
    InquiryTimeTo: Optional[str] = None
):
    """
    Helper that performs the Makeshop sync steps in a reusable way.
    """
    from datetime import datetime, timezone, timedelta
    from zoneinfo import ZoneInfo

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))

    sync_window_meta: dict[str, str] = {}
    InquiryTimeFrom, InquiryTimeTo, sync_window_meta = resolve_order_sync_window(
        now_kst,
        InquiryTimeFrom,
        InquiryTimeTo,
    )
    print(
        f"[통합 동기화] 주문 구간({sync_window_meta.get('mode', 'unknown')}): "
        f"{InquiryTimeFrom} ~ {InquiryTimeTo}"
    )

    results: dict[str, object] = {
        "status": "success",
        "service": "babba-sync-makeshop-all",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sync_window": sync_window_meta,
        "synced_data": {}
    }

    try:
        print("\n" + "="*60)
        print("[통합 동기화] Step 1: 상품 동기화 시작")
        print("="*60)

        try:
            products_response: object = sync_makeshop_products(db=db)
            results["synced_data"] = {**results["synced_data"], "products": products_response}  # type: ignore
            print(f"[통합 동기화] 상품 동기화 완료: {products_response}")
        except Exception as e:
            print(f"[통합 동기화] 상품 동기화 실패: {str(e)}")
            results["synced_data"] = {**results["synced_data"], "products": {
                "status": "error",
                "error": str(e)
            }}

        print("\n" + "="*60)
        print("[통합 동기화] Step 2: 회원 동기화 시작")
        print("="*60)

        try:
            members_response: object = sync_makeshop_members(db=db)
            results["synced_data"] = {**results["synced_data"], "members": members_response}  # type: ignore
            print(f"[통합 동기화] 회원 동기화 완료: {members_response}")
        except Exception as e:
            print(f"[통합 동기화] 회원 동기화 실패: {str(e)}")
            results["synced_data"] = {**results["synced_data"], "members": {
                "status": "error",
                "error": str(e)
            }}

        print("\n" + "="*60)
        print("[통합 동기화] Step 3: 주문 동기화 시작")
        print("="*60)

        try:
            print(f"[주문 동기화] 시작: {InquiryTimeFrom} ~ {InquiryTimeTo}")
            orders_response: object = sync_makeshop_orders(
                db=db,
                InquiryTimeFrom=InquiryTimeFrom,
                InquiryTimeTo=InquiryTimeTo
            )
            results["synced_data"] = {**results["synced_data"], "orders": orders_response}  # type: ignore
            print(f"[통합 동기화] 주문 동기화 완료: {orders_response}")
        except Exception as e:
            print(f"[통합 동기화] 주문 동기화 실패: {str(e)}")
            results["synced_data"] = {**results["synced_data"], "orders": {
                "status": "error",
                "error": str(e)
            }}

        print("\n" + "="*60)
        print("[통합 동기화] 모든 동기화 작업 완료")
        print("="*60)

        # Step 4: 정산 사전 검증 (동기화 완료 후 자동 실행)
        print("\n" + "="*60)
        print("[통합 동기화] Step 4: 정산 사전 검증 시작")
        print("="*60)

        try:
            from app.services.settlement_service import SettlementService
            from app.database import SessionLocal as _SessionLocal

            validate_db = _SessionLocal()
            try:
                validate_result = SettlementService.pre_validate_orders(db=validate_db)
                issue_count = validate_result.get('issue_count', 0)
                total_orders = validate_result.get('total_completed_orders', 0)
                settleable = validate_result.get('settleable_count', 0)
                summary = validate_result.get('summary_by_reason', {})

                results["synced_data"] = {**results["synced_data"], "pre_validation": {  # type: ignore
                    "total_completed_orders": total_orders,
                    "settleable_count": settleable,
                    "issue_count": issue_count,
                    "summary_by_reason": summary,
                }}

                if issue_count > 0:
                    print(f"\n[정산 사전 검증] ⚠️ 정산 불가 주문 {issue_count}건 발견 (총 {total_orders}건 중, 정산 가능: {settleable}건)")
                    print("-" * 60)

                    # 사유별 한글 설명
                    reason_labels = {
                        'USER_NOT_FOUND': '사용자 매핑 불가',
                        'INVALID_COMPANY_ID': '회사ID 오류',
                        'NO_ORDER_ITEMS': '주문 상품 없음',
                        'NO_PRODUCT': '상품 정보 없음',
                        'NO_COMMISSION_TYPE': '수수료 타입 미설정',
                    }

                    for reason, count in summary.items():
                        label = reason_labels.get(reason, reason)
                        print(f"\n  📌 {label} ({reason}): {count}건")

                    # 건별 상세 로그
                    print("\n" + "-" * 60)
                    print("[정산 사전 검증] 건별 상세 내역:")
                    print("-" * 60)
                    all_issues = validate_result.get('issues', [])
                    for idx, issue in enumerate(all_issues, 1):
                        print(f"  {idx}. {issue.get('detail', issue.get('reason', ''))}")

                    print("-" * 60)
                    print(f"[정산 사전 검증] 💡 위 문제를 해결하면 정산율이 {total_orders}건 중 {settleable}건 → {total_orders}건으로 개선됩니다.")
                    print(f"[정산 사전 검증] 관리자 패널 > 정산 안된 내역 메뉴에서도 확인할 수 있습니다.\n")
                else:
                    print(f"[정산 사전 검증] ✅ 모든 주문 정산 가능 ({total_orders}건)")
            finally:
                validate_db.close()
        except Exception as e:
            print(f"[정산 사전 검증] 검증 실패 (동기화 결과에 영향 없음): {str(e)}")
            results["synced_data"] = {**results["synced_data"], "pre_validation": {  # type: ignore
                "status": "error",
                "error": str(e),
            }}

        print(f"결과: {results}")

        return results

    except Exception as e:
        print(f"[통합 동기화] 오류 발생: {str(e)}")
        results["status"] = "error"
        results["error"] = str(e)
        return results


@app.post("/sync/makeshop/all", tags=["Makeshop Sync"])
def sync_makeshop_all(
    db: Session = Depends(get_db),
    InquiryTimeFrom: Optional[str] = None,
    InquiryTimeTo: Optional[str] = None
):
    return _run_makeshop_sync(db, InquiryTimeFrom, InquiryTimeTo)


class MakeshopSyncTaskPayload(BaseModel):
    InquiryTimeFrom: Optional[str] = None
    InquiryTimeTo: Optional[str] = None


def _enqueue_makeshop_sync_task(base_url: str, payload: MakeshopSyncTaskPayload) -> str:
    """Cloud Tasks 큐에 작업 추가. 서비스 계정 권한으로 실행"""
    try:
        from google.auth import default
        from google.auth.transport.requests import Request
        
        logger.info("[CT] 자격증명 로드 및 갱신...")
        credentials, project = default()
        
        # 자격증명 갱신 (권한 변경사항 반영)
        request = Request()
        if hasattr(credentials, 'refresh'):
            credentials.refresh(request)
        
        logger.info(f"[CT] 프로젝트: {project}")
        sa_email = getattr(credentials, "service_account_email", None)
        if sa_email:
            logger.info(f"[CT] ADC 서비스 계정: {sa_email}")
        
        client = tasks_v2.CloudTasksClient(credentials=credentials)
        queue = client.queue_path(PROJECT_ID, TASKS_QUEUE_LOCATION, TASKS_QUEUE_NAME)
        url = f"{base_url.rstrip('/')}{TASKS_BACKGROUND_PATH}"
        body = json.dumps(payload.model_dump(exclude_none=True)).encode("utf-8")
        
        logger.info(f"[CT] 큐: {queue}, URL: {url}")
        
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": body
            }
        }

        logger.info("[CT] 작업 생성...")
        created = client.create_task(parent=queue, task=task)
        logger.info(f"[CT] ✓ 성공: {created.name}")
        return created.name
        
    except Exception as e:
        logger.error(f"[CT] ✗ 실패: {e}", exc_info=True)
        raise


@app.post("/tasks/sync/makeshop/trigger", tags=["Makeshop Sync"])
def trigger_makeshop_sync(
    request: Request,
    InquiryTimeFrom: Optional[str] = None,
    InquiryTimeTo: Optional[str] = None
):
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    payload = MakeshopSyncTaskPayload(
        InquiryTimeFrom=InquiryTimeFrom,
        InquiryTimeTo=InquiryTimeTo
    )
    task_name = _enqueue_makeshop_sync_task(base_url, payload)
    return {
        "status": "queued",
        "task": task_name,
        "payload": payload.model_dump(exclude_none=True)
    }


@app.post("/tasks/sync/makeshop/run", tags=["Makeshop Sync"])
def run_makeshop_sync_task(
    payload: MakeshopSyncTaskPayload,
    db: Session = Depends(get_db)
):
    return _run_makeshop_sync(db, payload.InquiryTimeFrom, payload.InquiryTimeTo)


@app.post("/sync/makeshop/products", tags=["Makeshop Sync"]) 
def sync_makeshop_products(db: Session = Depends(get_db)):
    """
    Makeshop에서 상품 정보를 모두 동기화합니다. (페이지네이션 기반)
    
    동기화 로직:
    1. API에서 limit=1000으로 첫 페이지 조회
    2. 응답의 totalCount와 현재까지 조회한 상품 수(count * page)를 비교
    3. totalCount > count * page 이면 page++ 하여 다음 페이지 조회
    4. 모든 페이지를 조회할 때까지 반복
    5. 기존 상품과 비교하여 신규/수정 구분 후 DB에 저장
    
    Makeshop API 응답 구조:
    {
        "return_code": "0000",
        "totalCount": "1234",    # 전체 상품 수
        "totalPage": 2,          # 전체 페이지 수
        "page": 1,               # 현재 페이지
        "count": 1000,           # 현재 페이지의 상품 수
        "list": [{...}, {...}]   # 상품 목록
    }
    
    Returns:
        동기화 결과 (총 처리 수, 신규 추가, 업데이트 수, 조회한 페이지 수)
    
    Example:
        POST /sync/makeshop/products
    """
    from app.services.makeshop_rest_stats import rest_call_stats_scope

    _rest_cm = rest_call_stats_scope()
    rest_stats = _rest_cm.__enter__()
    try:
        total_count = 0
        created_count = 0
        updated_count = 0
        limit = 1000  # 한 번에 조회할 상품 수
        page = 1
        total_pages_fetched = 0
        all_products_synced = False
        api_mode = "REST" if use_makeshop_rest() else "legacy"

        print(f"[상품 동기화] 시작: 전체 상품을 limit=1000으로 조회 ({api_mode})")
        
        # 페이지네이션 루프
        while not all_products_synced:
            print(f"[상품 동기화] 페이지 {page} 조회 중 (limit={limit})")
            
            try:
                response_data = fetch_products_page(page=page, limit=limit, db=db)
                products = response_data.get("list", [])
            except MakeshopAPIError as e:
                error_message = f"Makeshop API 오류: [{e.return_code}] {e.message}"
                print(f"[상품 동기화 실패] {error_message}")
                db.rollback()
                raise HTTPException(status_code=400, detail=error_message)
            
            if not products:
                print(f"[상품 동기화] 페이지 {page}: 조회된 상품이 없음")
                break
            
            # 각 상품 처리
            for product_data in products:
                # Makeshop API 응답에서 상품 ID 추출 (uid)
                product_id = product_data.get("uid")
                
                if not product_id:
                    print(f"[상품 동기화 경고] 상품 ID 없음: {product_data}")
                    continue

                # 기존 상품 확인
                db_product = db.query(Product).filter(
                    Product.uid == product_id
                ).first()

                if db_product:
                    # 기존 상품 업데이트
                    db_product.product_name = safe_string(product_data.get("product_name")) or db_product.product_name
                    db_product.sellprice = safe_int(product_data.get("sellprice")) or db_product.sellprice
                    db_product.buyprice = safe_int(product_data.get("buyprice")) or db_product.buyprice
                    db_product.consumerprice = safe_int(product_data.get("consumerprice")) or db_product.consumerprice
                    db_product.quantity = parse_quantity(product_data.get("quantity", 0))
                    db_product.status = safe_string(product_data.get("status")) or db_product.status
                    # Extended fields (확장 필드) - Makeshop API와 동기화
                    db_product.brandcode = safe_string(product_data.get("brandcode")) or db_product.brandcode
                    db_product.cate1 = safe_string(product_data.get("cate1")) or db_product.cate1
                    db_product.cate2 = safe_string(product_data.get("cate2")) or db_product.cate2
                    db_product.virtual_cate = safe_string(product_data.get("virtual_cate")) or db_product.virtual_cate
                    db_product.reserve = safe_string(product_data.get("reserve")) or db_product.reserve
                    db_product.keyword = safe_string(product_data.get("keyword")) or db_product.keyword
                    db_product.sell_accept = safe_string(product_data.get("sell_accept")) or db_product.sell_accept
                    db_product.display = safe_string(product_data.get("display")) or db_product.display
                    db_product.product_type = safe_string(product_data.get("product_type")) or db_product.product_type
                    db_product.best_product_display = safe_string(product_data.get("best_product_display")) or db_product.best_product_display
                    db_product.best_review_display = safe_string(product_data.get("best_review_display")) or db_product.best_review_display
                    db_product.sellcount = safe_int(product_data.get("sellcount")) or db_product.sellcount
                    db_product.regdate = safe_string(product_data.get("regdate")) or db_product.regdate
                    db_product.moddate = safe_string(product_data.get("moddate")) or db_product.moddate
                    db_product.provide_delivery_price = safe_int(product_data.get("provide_delivery_price")) or db_product.provide_delivery_price
                    db_product.max_order_quantity_method = safe_string(product_data.get("max_order_quantity_method")) or db_product.max_order_quantity_method
                    db_product.min_order_quantity_method = safe_string(product_data.get("min_order_quantity_method")) or db_product.min_order_quantity_method
                    db_product.vat = safe_string(product_data.get("vat")) or db_product.vat
                    db_product.vat_type = safe_string(product_data.get("vat_type")) or db_product.vat_type
                    db_product.product_content = safe_string(product_data.get("product_content")) or db_product.product_content
                    db_product.display_date = safe_string(product_data.get("display_date")) or db_product.display_date
                    db_product.importune = safe_string(product_data.get("importune")) or db_product.importune
                    db_product.view_count = safe_int(product_data.get("view_count")) or db_product.view_count
                    db_product.cart_count = safe_int(product_data.get("cart_count")) or db_product.cart_count
                    db_product.is_add_composition = safe_string(product_data.get("is_add_composition")) or db_product.is_add_composition
                    db_product.ems_type = safe_string(product_data.get("ems_type")) or db_product.ems_type
                    updated_count += 1
                else:
                    # 신규 상품 생성
                    db_product = Product(
                        uid=product_id,
                        product_name=safe_string(product_data.get("product_name", "")),
                        sellprice=safe_int(product_data.get("sellprice")) or 0,
                        buyprice=safe_int(product_data.get("buyprice")),
                        consumerprice=safe_int(product_data.get("consumerprice")),
                        quantity=parse_quantity(product_data.get("quantity", 0)),
                        status=safe_string(product_data.get("status", "active")),
                        # Extended fields (확장 필드) - Makeshop API와 동기화
                        brandcode=safe_string(product_data.get("brandcode")),
                        cate1=safe_string(product_data.get("cate1")),
                        cate2=safe_string(product_data.get("cate2")),
                        virtual_cate=safe_string(product_data.get("virtual_cate")),
                        reserve=safe_string(product_data.get("reserve")),
                        keyword=safe_string(product_data.get("keyword")),
                        sell_accept=safe_string(product_data.get("sell_accept")),
                        display=safe_string(product_data.get("display")),
                        product_type=safe_string(product_data.get("product_type")),
                        best_product_display=safe_string(product_data.get("best_product_display")),
                        best_review_display=safe_string(product_data.get("best_review_display")),
                        sellcount=safe_int(product_data.get("sellcount")),
                        regdate=safe_string(product_data.get("regdate")),
                        moddate=safe_string(product_data.get("moddate")),
                        provide_delivery_price=safe_int(product_data.get("provide_delivery_price")),
                        max_order_quantity_method=safe_string(product_data.get("max_order_quantity_method")),
                        min_order_quantity_method=safe_string(product_data.get("min_order_quantity_method")),
                        vat=safe_string(product_data.get("vat")),
                        vat_type=safe_string(product_data.get("vat_type")),
                        product_content=safe_string(product_data.get("product_content")),
                        display_date=safe_string(product_data.get("display_date")),
                        importune=safe_string(product_data.get("importune")),
                        view_count=safe_int(product_data.get("view_count")),
                        cart_count=safe_int(product_data.get("cart_count")),
                        is_add_composition=safe_string(product_data.get("is_add_composition")),
                        ems_type=safe_string(product_data.get("ems_type"))
                    )
                    db.add(db_product)
                    created_count += 1

                total_count += 1

            # DB에 변경사항 저장 (매 페이지마다)
            db.commit()
            
            print(f"[상품 동기화] 페이지 {page} 완료: {len(products)}개 처리 (신규: {created_count}, 수정: {updated_count})")
            total_pages_fetched += 1
            
            # 다음 페이지 존재 여부 확인
            total_count_api = int(response_data.get("totalCount", 0))
            current_count = page * limit
            
            print(f"[상품 동기화 진행상황] 총 {total_count_api}개 중 {current_count}개 조회 완료")
            
            if current_count >= total_count_api:
                # 모든 상품을 조회 완료
                print(f"[상품 동기화] 모든 상품 조회 완료 (총 {total_count_api}개)")
                all_products_synced = True
            else:
                # 다음 페이지가 있음
                page += 1

        result = {
            "status": "success",
            "message": "상품 동기화 완료",
            "api_mode": api_mode,
            "total_processed": total_count,
            "created": created_count,
            "updated": updated_count,
            "total_pages": total_pages_fetched,
            "limit": limit,
            "rest_stats": rest_stats.snapshot(),
        }
        try:
            from app.services.google_chat import notify_makeshop_sync_result

            notify_makeshop_sync_result(
                resource="products",
                success=True,
                api_mode=api_mode,
                total_processed=total_count,
                created=created_count,
                updated=updated_count,
                total_pages=total_pages_fetched,
                rest_stats=rest_stats.snapshot(),
            )
        except Exception as chat_exc:  # noqa: BLE001
            print(f"[상품 동기화] Google Chat 알림 실패: {chat_exc}")
        return result

    except ValueError as e:
        db.rollback()
        try:
            from app.services.google_chat import notify_makeshop_sync_result

            notify_makeshop_sync_result(
                resource="products",
                success=False,
                error=f"설정 오류: {e}",
                rest_stats=rest_stats.snapshot(),
            )
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"설정 오류: {str(e)}")
    except HTTPException as e:
        try:
            from app.services.google_chat import notify_makeshop_sync_result

            notify_makeshop_sync_result(
                resource="products",
                success=False,
                error=str(e.detail),
                rest_stats=rest_stats.snapshot(),
            )
        except Exception:
            pass
        raise
    except Exception as e:
        db.rollback()
        try:
            from app.services.google_chat import notify_makeshop_sync_result

            notify_makeshop_sync_result(
                resource="products",
                success=False,
                error=f"동기화 실패: {e}",
                rest_stats=rest_stats.snapshot(),
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")
    finally:
        _rest_cm.__exit__(None, None, None)


@app.post("/sync/makeshop/orders", tags=["Makeshop Sync"]) 
def sync_makeshop_orders(
    db: Session = Depends(get_db),
    InquiryTimeFrom: str = "2025-01-01 00:00:00",
    InquiryTimeTo: str = None
):
    """
    Makeshop에서 주문 정보를 동기화합니다.

    - 기본(스케줄/센티널 From): 최근 30일
    - 조회 구간은 일 단위로 나눠 호출 (주문 2.0 권장, totalCount 누락 완화)
    - 페이지는 누적 건수 기준으로 다음 페이지 판단 (`page * limit` 조기종료 버그 수정)
    """
    from app.services.makeshop_rest_stats import rest_call_stats_scope

    _rest_cm = rest_call_stats_scope()
    rest_stats = _rest_cm.__enter__()
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
        InquiryTimeFrom, InquiryTimeTo, sync_window_meta = resolve_order_sync_window(
            now_kst,
            InquiryTimeFrom,
            InquiryTimeTo,
        )

        total_count = 0
        created_count = 0
        updated_count = 0
        limit = 1000
        total_pages_fetched = 0
        windows_fetched = 0
        api_mode = "REST" if use_makeshop_rest() else "legacy"
        day_windows = list(iter_inquiry_day_windows(InquiryTimeFrom, InquiryTimeTo))

        print(
            f"[주문 동기화] 시작: {InquiryTimeFrom} ~ {InquiryTimeTo} "
            f"({api_mode}, windows={len(day_windows)}, meta={sync_window_meta})"
        )

        for win_from, win_to in day_windows:
            windows_fetched += 1
            page = 1
            fetched_in_window = 0
            print(f"[주문 동기화] 구간 {windows_fetched}/{len(day_windows)}: {win_from} ~ {win_to}")

            while True:
                print(f"[주문 동기화] 페이지 {page} 조회 중 (limit={limit})")

                try:
                    response_data = fetch_orders_page(
                        page=page,
                        limit=limit,
                        inquiry_time_from=win_from,
                        inquiry_time_to=win_to,
                        db=db,
                    )
                    orders = response_data.get("list", []) or {}
                except MakeshopAPIError as e:
                    error_message = f"Makeshop API 오류: [{e.return_code}] {e.message}"
                    print(f"[주문 동기화 실패] {error_message}")
                    db.rollback()
                    raise HTTPException(status_code=400, detail=error_message)

                if not orders:
                    print(f"[주문 동기화] 페이지 {page}: 조회된 주문이 없음")
                    break

                if not isinstance(orders, dict):
                    print(f"[주문 동기화 경고] list 형태 이상: {type(orders)}")
                    break

                for _order_id_key, order_wrapper in orders.items():
                    if not isinstance(order_wrapper, dict):
                        continue

                    order_data = order_wrapper.get("order", {})
                    payment_data = order_wrapper.get("payment", {})
                    product_data = order_wrapper.get("product", {})

                    ordernum = order_data.get("ordernum")
                    if not ordernum:
                        print("[주문 동기화 경고] 주문 번호 없음")
                        continue

                    db_order = db.query(Order).filter(
                        Order.ordernum == ordernum
                    ).first()

                    shipping_address = None
                    if isinstance(product_data, dict):
                        first_product = next(iter(product_data.values()), None) if product_data else None
                        if first_product:
                            delivery_info = first_product.get("deliveryInfo", {})
                            if isinstance(delivery_info, dict):
                                post = delivery_info.get("post", "")
                                address = delivery_info.get("address", "")
                                address_detail = delivery_info.get("address2", "")
                                shipping_address = f"[{post}] {address} {address_detail}".strip()

                    if db_order:
                        db_order.member_id = safe_string(order_data.get("id")) or db_order.member_id
                        db_order.sender = safe_string(order_data.get("sender")) or db_order.sender
                        db_order.email = safe_string(order_data.get("email")) or db_order.email
                        db_order.phone = safe_string(order_data.get("phone")) or db_order.phone
                        db_order.mobile = safe_string(order_data.get("mobile")) or db_order.mobile
                        db_order.pay_price = safe_int(order_data.get("pay_price")) or db_order.pay_price
                        db_order.pay_status = safe_string(payment_data.get("pay_status")) or db_order.pay_status
                        db_order.order_status = safe_string(order_data.get("order_status")) or db_order.order_status
                        db_order.basket_count = safe_int(order_data.get("basket_count")) or (
                            len(product_data) if isinstance(product_data, dict) else db_order.basket_count
                        )
                        db_order.shipping_address = shipping_address or db_order.shipping_address
                        db_order.memo = safe_string(order_data.get("memo")) or db_order.memo
                        db_order.order_date = safe_string(order_data.get("order_date")) or db_order.order_date
                        db_order.is_member = safe_int(order_data.get("is_member")) or db_order.is_member
                        db_order.pay_path = safe_string(order_data.get("pay_path")) or db_order.pay_path
                        db_order.deli_price = safe_int(order_data.get("deli_price")) or db_order.deli_price
                        db_order.start_price = safe_int(order_data.get("start_price")) or db_order.start_price
                        db_order.total_product_price = safe_int(order_data.get("total_product_price")) or db_order.total_product_price
                        db_order.used_emoney = safe_int(order_data.get("used_emoney")) or db_order.used_emoney
                        db_order.used_reserve = safe_int(order_data.get("used_reserve")) or db_order.used_reserve
                        db_order.group_name = safe_string(order_data.get("group_name")) or db_order.group_name
                        db_order.cash_receipt = safe_string(order_data.get("cash_receipt")) or db_order.cash_receipt
                        db_order.cash_receipt_status = safe_string(order_data.get("cash_receipt_status")) or db_order.cash_receipt_status
                        updated_count += 1
                    else:
                        db_order = Order(
                            ordernum=ordernum,
                            member_id=safe_string(order_data.get("id")),
                            order_date=safe_string(order_data.get("order_date")),
                            is_member=safe_int(order_data.get("is_member")) or 0,
                            sender=safe_string(order_data.get("sender")),
                            email=safe_string(order_data.get("email")),
                            phone=safe_string(order_data.get("phone")),
                            mobile=safe_string(order_data.get("mobile")),
                            pay_path=safe_string(order_data.get("pay_path")),
                            pay_price=safe_int(order_data.get("pay_price")) or 0,
                            order_status=safe_string(order_data.get("order_status")) or "pending",
                            pay_status=safe_string(payment_data.get("pay_status")) or "pending",
                            deli_price=safe_int(order_data.get("deli_price")) or 0,
                            start_price=safe_int(order_data.get("start_price")) or 0,
                            total_product_price=safe_int(order_data.get("total_product_price")) or 0,
                            basket_count=safe_int(order_data.get("basket_count")) or (
                                len(product_data) if isinstance(product_data, dict) else 0
                            ),
                            memo=safe_string(order_data.get("memo")),
                            used_emoney=safe_int(order_data.get("used_emoney")) or 0,
                            used_reserve=safe_int(order_data.get("used_reserve")) or 0,
                            group_name=safe_string(order_data.get("group_name")),
                            cash_receipt=safe_string(order_data.get("cash_receipt")),
                            cash_receipt_status=safe_string(order_data.get("cash_receipt_status")),
                            shipping_address=shipping_address
                        )
                        db.add(db_order)
                        created_count += 1

                    if isinstance(product_data, dict):
                        existing_items = db.query(OrderItem).filter(OrderItem.ordernum == ordernum).all()
                        item_map = {item.product_uid: item for item in existing_items}
                        processed_uids = set()

                        for item_index, (_key, product_item) in enumerate(product_data.items()):
                            if isinstance(product_item, dict):
                                product_uid = safe_string(product_item.get("product_uid")) or f"UNKNOWN_{item_index}"
                                processed_uids.add(product_uid)

                                if product_uid in item_map:
                                    item = item_map[product_uid]
                                    item.product_name = safe_string(product_item.get("product_name")) or item.product_name
                                    item.basket_stock = safe_int(product_item.get("basket_stock")) or item.basket_stock
                                    item.sell_price = safe_int(product_item.get("sell_price")) or item.sell_price
                                    item.num = safe_string(product_item.get("num")) or item.num
                                    item.cate1 = safe_string(product_item.get("cate1")) or item.cate1
                                    item.basket_status = safe_string(product_item.get("basket_status")) or item.basket_status
                                    item.stock_key = safe_string(product_item.get("stock_key")) or item.stock_key
                                    item.vat = safe_int(product_item.get("vat")) or item.vat
                                else:
                                    order_item = OrderItem(
                                        ordernum=ordernum,
                                        product_uid=product_uid,
                                        product_name=safe_string(product_item.get("product_name")) or "상품명 없음",
                                        basket_stock=safe_int(product_item.get("basket_stock")) or 1,
                                        sell_price=safe_int(product_item.get("sell_price")) or 0,
                                        num=safe_string(product_item.get("num")),
                                        cate1=safe_string(product_item.get("cate1")),
                                        basket_status=safe_string(product_item.get("basket_status")),
                                        stock_key=safe_string(product_item.get("stock_key")),
                                        vat=safe_int(product_item.get("vat")) or 0,
                                    )
                                    db.add(order_item)

                        for uid, item in item_map.items():
                            if uid not in processed_uids:
                                db.delete(item)

                    total_count += 1

                db.commit()

                page_count = len(orders)
                fetched_in_window += page_count
                total_pages_fetched += 1
                try:
                    total_count_api = int(response_data.get("totalCount") or 0)
                except (TypeError, ValueError):
                    total_count_api = 0

                print(
                    f"[주문 동기화] 페이지 {page} 완료: {page_count}개 "
                    f"(구간누적 {fetched_in_window}/{total_count_api or '?'}, "
                    f"전체 신규:{created_count} 수정:{updated_count})"
                )

                if not should_fetch_next_order_page(
                    page_count=page_count,
                    limit=limit,
                    fetched_in_window=fetched_in_window,
                    total_count_api=total_count_api,
                ):
                    break
                page += 1
                if page > 200:
                    print("[주문 동기화 경고] 페이지 상한(200) 도달 — 구간 종료")
                    break

        result = {
            "status": "success",
            "message": "주문 동기화 완료",
            "api_mode": api_mode,
            "sync_window": sync_window_meta,
            "inquiry_from": InquiryTimeFrom,
            "inquiry_to": InquiryTimeTo,
            "windows": windows_fetched,
            "total_processed": total_count,
            "created": created_count,
            "updated": updated_count,
            "total_pages": total_pages_fetched,
            "limit": limit,
        }
        try:
            from app.services.google_chat import notify_order_sync_result

            notify_order_sync_result(
                success=True,
                inquiry_from=InquiryTimeFrom,
                inquiry_to=InquiryTimeTo,
                api_mode=api_mode,
                windows=windows_fetched,
                total_processed=total_count,
                created=created_count,
                updated=updated_count,
                total_pages=total_pages_fetched,
                sync_window=sync_window_meta,
                rest_stats=rest_stats.snapshot(),
            )
        except Exception as chat_exc:  # noqa: BLE001
            print(f"[주문 동기화] Google Chat 알림 실패: {chat_exc}")
        return result

    except ValueError as e:
        db.rollback()
        try:
            from app.services.google_chat import notify_order_sync_result

            notify_order_sync_result(
                success=False,
                error=f"설정 오류: {e}",
                rest_stats=rest_stats.snapshot(),
            )
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"설정 오류: {str(e)}")
    except HTTPException as e:
        try:
            from app.services.google_chat import notify_order_sync_result

            notify_order_sync_result(
                success=False,
                error=str(e.detail),
                rest_stats=rest_stats.snapshot(),
            )
        except Exception:
            pass
        raise
    except Exception as e:
        db.rollback()
        try:
            from app.services.google_chat import notify_order_sync_result

            notify_order_sync_result(
                success=False,
                error=f"동기화 실패: {e}",
                rest_stats=rest_stats.snapshot(),
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")
    finally:
        _rest_cm.__exit__(None, None, None)


@app.post("/sync/makeshop/members", tags=["Makeshop Sync"]) 
def sync_makeshop_members(db: Session = Depends(get_db)):
    """
    Makeshop에서 회원 정보를 모두 동기화합니다. (페이지네이션 기반)
    
    📋 동기화 로직:
    1. Makeshop API에서 limit=5000으로 첫 페이지 조회
    2. 응답의 totalCount와 현재까지 조회한 회원 수(count * page)를 비교
    3. totalCount > count * page 이면 page++ 하여 다음 페이지 조회
    4. 모든 페이지를 조회할 때까지 반복
    5. 기존 회원과 비교하여 신규 추가/업데이트 구분 후 DB에 저장
    
    🔧 Makeshop API 파라미터:
    - **page**: 페이지 번호 (1부터 시작)
    - **limit**: 한 번에 조회할 회원 수 (기본 5000)
    - **mode**: "search"
    - **type**: "user"
    
    📊 반환 필드:
    - **total_processed**: 처리된 총 회원 수
    - **created**: 신규 추가된 회원 수
    - **updated**: 업데이트된 회원 수
    - **total_pages**: 조회한 총 페이지 수
    - **limit**: 페이지당 조회 건수
    
    ⚠️ 주의사항:
    - 회원 데이터가 많으면 오래 걸릴 수 있습니다
    - 배치 단위로 DB에 저장합니다 (페이지마다)
    
    Example:
        POST /sync/makeshop/members
    """
    from app.services.makeshop_rest_stats import rest_call_stats_scope

    _rest_cm = rest_call_stats_scope()
    rest_stats = _rest_cm.__enter__()
    try:
        total_count = 0
        created_count = 0
        updated_count = 0
        # REST는 limit 상한이 있어 1000으로 맞춤 (페이지네이션 계산과 일치)
        limit = 1000 if use_makeshop_rest() else 5000
        page = 1
        total_pages_fetched = 0
        all_members_synced = False
        api_mode = "REST" if use_makeshop_rest() else "legacy"

        print(f"[회원 동기화] 시작: 페이지네이션 기반 회원 조회 ({api_mode})")
        
        # 페이지네이션 루프
        while not all_members_synced:
            print(f"[회원 동기화] 페이지 {page} 조회 중 (limit={limit})")
            
            try:
                response_data = fetch_members_page(page=page, limit=limit, db=db)
                members = response_data.get("list", [])
            except MakeshopAPIError as e:
                error_message = f"Makeshop API 오류: [{e.return_code}] {e.message}"
                print(f"[회원 동기화 실패] {error_message}")
                db.rollback()
                raise HTTPException(status_code=400, detail=error_message)
            
            if not members:
                print(f"[회원 동기화] 페이지 {page}: 조회된 회원이 없음")
                break
            
            # 각 회원 처리
            for member_data in members:
                member_id = member_data.get("id")

                # 기존 회원 확인
                db_member = db.query(Member).filter(
                    Member.makeshop_member_id == member_id
                ).first()

                if db_member:
                    # 기존 회원 업데이트
                    db_member.hname = member_data.get("hname", db_member.hname)  # API: hname
                    db_member.email = member_data.get("email", db_member.email)
                    db_member.mobile = member_data.get("mobile", db_member.mobile)  # API: mobile
                    db_member.address = member_data.get("address", db_member.address)
                    db_member.member_level = member_data.get("group_name", db_member.member_level)
                    db_member.total_orders = member_data.get("order_count", db_member.total_orders)
                    # Extended fields
                    db_member.mem_type = member_data.get("mem_type", db_member.mem_type)
                    db_member.simple_type = member_data.get("simple_type", db_member.simple_type)
                    db_member.grade = member_data.get("grade", db_member.grade)
                    db_member.reserve = member_data.get("reserve", db_member.reserve)
                    db_member.email_receive = member_data.get("email_receive", db_member.email_receive)
                    db_member.sms_receive = member_data.get("sms_receive", db_member.sms_receive)
                    db_member.login_date = member_data.get("login_date", db_member.login_date)
                    db_member.mod_date = member_data.get("mod_date", db_member.mod_date)
                    db_member.reg_date = member_data.get("reg_date", db_member.reg_date)
                    db_member.birth_day = member_data.get("birth_day", db_member.birth_day)
                    db_member.birth_day_year = member_data.get("birth_day_year", db_member.birth_day_year)
                    db_member.birth_format = member_data.get("birth_format", db_member.birth_format)
                    db_member.sex = member_data.get("sex", db_member.sex)
                    db_member.group_id = member_data.get("group_id", db_member.group_id)
                    db_member.group_name = member_data.get("group_name", db_member.group_name)
                    db_member.post = member_data.get("post", db_member.post)
                    db_member.address_detail = member_data.get("address_detail", db_member.address_detail)
                    db_member.push_receive = member_data.get("push_receive", db_member.push_receive)
                    db_member.point = member_data.get("point", db_member.point)
                    db_member.emoney = member_data.get("emoney", db_member.emoney)
                    db_member.is_app_use = member_data.get("is_app_use", db_member.is_app_use)
                    db_member.extension_period = member_data.get("extension_period", db_member.extension_period)
                    db_member.order_count = member_data.get("order_count", db_member.order_count)
                    # Company info
                    company_info = member_data.get("company_info", {})
                    if isinstance(company_info, dict):
                        db_member.company_name = company_info.get("company_name", db_member.company_name)
                        db_member.company_owner = company_info.get("company_owner", db_member.company_owner)
                        db_member.company_num = company_info.get("company_num", db_member.company_num)
                        db_member.company_corp = company_info.get("company_corp", db_member.company_corp)
                        db_member.company_biz = company_info.get("company_biz", db_member.company_biz)
                        db_member.company_item = company_info.get("company_item", db_member.company_item)
                        db_member.company_post = company_info.get("company_post", db_member.company_post)
                        db_member.company_addr = company_info.get("company_addr", db_member.company_addr)
                    updated_count += 1
                else:
                    # 신규 회원 생성
                    company_info = member_data.get("company_info", {})
                    db_member = Member(
                        makeshop_member_id=member_id,
                        hname=member_data.get("hname", ""),  # API: hname
                        email=member_data.get("email"),
                        mobile=member_data.get("mobile"),  # API: mobile
                        address=member_data.get("address"),
                        member_level=member_data.get("group_name"),
                        total_orders=member_data.get("order_count", 0),
                        # Extended fields
                        mem_type=member_data.get("mem_type"),
                        simple_type=member_data.get("simple_type"),
                        grade=member_data.get("grade"),
                        reserve=member_data.get("reserve"),
                        email_receive=member_data.get("email_receive"),
                        sms_receive=member_data.get("sms_receive"),
                        login_date=member_data.get("login_date"),
                        mod_date=member_data.get("mod_date"),
                        reg_date=member_data.get("reg_date"),
                        birth_day=member_data.get("birth_day"),
                        birth_day_year=member_data.get("birth_day_year"),
                        birth_format=member_data.get("birth_format"),
                        sex=member_data.get("sex"),
                        group_id=member_data.get("group_id"),
                        group_name=member_data.get("group_name"),
                        post=member_data.get("post"),
                        address_detail=member_data.get("address_detail"),
                        push_receive=member_data.get("push_receive"),
                        point=member_data.get("point"),
                        emoney=member_data.get("emoney"),
                        is_app_use=member_data.get("is_app_use"),
                        extension_period=member_data.get("extension_period"),
                        order_count=member_data.get("order_count"),
                        # Company info
                        company_name=company_info.get("company_name") if isinstance(company_info, dict) else None,
                        company_owner=company_info.get("company_owner") if isinstance(company_info, dict) else None,
                        company_num=company_info.get("company_num") if isinstance(company_info, dict) else None,
                        company_corp=company_info.get("company_corp") if isinstance(company_info, dict) else None,
                        company_biz=company_info.get("company_biz") if isinstance(company_info, dict) else None,
                        company_item=company_info.get("company_item") if isinstance(company_info, dict) else None,
                        company_post=company_info.get("company_post") if isinstance(company_info, dict) else None,
                        company_addr=company_info.get("company_addr") if isinstance(company_info, dict) else None,
                    )
                    db.add(db_member)
                    created_count += 1

                total_count += 1

            # DB에 변경사항 저장 (매 페이지마다)
            db.commit()
            
            print(f"[회원 동기화] 페이지 {page} 완료: {len(members)}개 처리 (신규: {created_count}, 수정: {updated_count})")
            total_pages_fetched += 1
            
            # 다음 페이지 존재 여부 확인
            total_count_api = int(response_data.get("totalCount", 0))
            current_count = page * limit
            
            print(f"[회원 동기화 진행상황] 총 {total_count_api}개 중 {current_count}개 조회 완료")
            
            if current_count >= total_count_api:
                # 모든 회원을 조회 완료
                print(f"[회원 동기화] 모든 회원 조회 완료 (총 {total_count_api}개)")
                all_members_synced = True
            else:
                # 다음 페이지가 있음
                page += 1

        result = {
            "status": "success",
            "message": "회원 동기화 완료",
            "api_mode": api_mode,
            "total_processed": total_count,
            "created": created_count,
            "updated": updated_count,
            "total_pages": total_pages_fetched,
            "limit": limit,
            "rest_stats": rest_stats.snapshot(),
        }
        try:
            from app.services.google_chat import notify_makeshop_sync_result

            notify_makeshop_sync_result(
                resource="members",
                success=True,
                api_mode=api_mode,
                total_processed=total_count,
                created=created_count,
                updated=updated_count,
                total_pages=total_pages_fetched,
                rest_stats=rest_stats.snapshot(),
            )
        except Exception as chat_exc:  # noqa: BLE001
            print(f"[회원 동기화] Google Chat 알림 실패: {chat_exc}")
        return result

    except ValueError as e:
        db.rollback()
        try:
            from app.services.google_chat import notify_makeshop_sync_result

            notify_makeshop_sync_result(
                resource="members",
                success=False,
                error=f"설정 오류: {e}",
                rest_stats=rest_stats.snapshot(),
            )
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"설정 오류: {str(e)}")
    except HTTPException as e:
        try:
            from app.services.google_chat import notify_makeshop_sync_result

            notify_makeshop_sync_result(
                resource="members",
                success=False,
                error=str(e.detail),
                rest_stats=rest_stats.snapshot(),
            )
        except Exception:
            pass
        raise
    except Exception as e:
        db.rollback()
        try:
            from app.services.google_chat import notify_makeshop_sync_result

            notify_makeshop_sync_result(
                resource="members",
                success=False,
                error=f"동기화 실패: {e}",
                rest_stats=rest_stats.snapshot(),
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")
    finally:
        _rest_cm.__exit__(None, None, None)


@app.get("/makeshop/health", tags=["Makeshop Sync"]) 
def check_makeshop_api_health(db: Session = Depends(get_db)):
    """
    Makeshop API 연결 상태를 확인합니다. (기본: 신규 Open API / REST)
    
    Returns:
        API 헬스 체크 결과
    """
    try:
        is_healthy = makeshop_health_check(db=db)
        api_mode = "REST" if use_makeshop_rest() else "legacy"
        if is_healthy:
            return {
                "status": "healthy",
                "message": "Makeshop API 연결 정상",
                "makeshop_api": "connected",
                "api_mode": api_mode,
            }
        return {
            "status": "unhealthy",
            "message": "Makeshop API 연결 실패",
            "makeshop_api": "disconnected",
            "api_mode": api_mode,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"설정 오류: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"헬스 체크 실패: {str(e)}")


# ============================================================================
# Test Endpoints (For debugging and verification)
# ============================================================================

@app.get("/test/db-connection", tags=["Tests"])
def test_db_connection(db: Session = Depends(get_db)):
    """
    데이터베이스 연결을 테스트합니다.
    
    이 엔드포인트는:
    1. 데이터베이스 연결 확인
    2. SELECT 1 쿼리 실행
    3. 모든 테이블 확인
    4. 각 테이블의 데이터 개수 조회
    
    Returns:
        테스트 결과 (연결 상태, 테이블 정보, 데이터 개수)
    """
    try:
        from sqlalchemy import inspect, text
        
        # 1. 기본 연결 테스트
        result = db.execute(text("SELECT 1 as connection_test"))
        connection_result = result.scalar()
        
        # 2. 테이블 목록 조회
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        
        # 3. 각 테이블 정보 수집
        tables_info = []
        with engine.connect() as connection:
            for table_name in sorted(table_names):
                query = text(f"SELECT COUNT(*) as cnt FROM {table_name}")
                result = connection.execute(query)
                row_count = result.scalar()
                
                columns = inspector.get_columns(table_name)
                tables_info.append({
                    "name": table_name,
                    "columns_count": len(columns),
                    "rows_count": row_count
                })
        
        return {
            "status": "success",
            "message": "데이터베이스 연결 테스트 성공",
            "connection_test": connection_result == 1,
            "tables_found": len(table_names),
            "tables": tables_info
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"데이터베이스 연결 테스트 실패: {str(e)}"
        )


@app.get("/test/makeshop-api", tags=["Tests"])
def test_makeshop_api_connection(db: Session = Depends(get_db)):
    """
    Makeshop API 연결을 테스트합니다. (기본: 신규 Open API / REST)

    1. 환경 변수 로드 확인
    2. 상품 1건 조회
    3. 응답 코드 확인
    """
    try:
        import os
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=".env.makeshop")

        api_mode = "REST" if use_makeshop_rest() else "legacy"
        env_check = {
            "api_mode": api_mode,
            "client_id_set": bool(os.getenv("MAKESHOP_CLIENT_ID")),
            "client_secret_set": bool(os.getenv("MAKESHOP_CLIENT_SECRET")),
            "shop_uid": os.getenv("MAKESHOP_SHOP_UID"),
            "shopkey_set": bool(os.getenv("MAKESHOP_SHOPKEY")),
            "licensekey_set": bool(os.getenv("MAKESHOP_LICENSEKEY")),
            "api_url": os.getenv("MAKESHOP_API_URL"),
        }

        response_data = fetch_products_page(page=1, limit=1, db=db)
        return_code = str(response_data.get("return_code", "unknown"))
        ok = return_code in {"0000", "0", "1", "OK", "success"}

        return {
            "status": "success" if ok else "failed",
            "message": "Makeshop API 테스트 완료",
            "environment": env_check,
            "api_mode": api_mode,
            "api_response": {
                "return_code": return_code,
                "count": response_data.get("count"),
                "totalCount": response_data.get("totalCount"),
                "list_len": len(response_data.get("list") or []),
            },
            "return_code": return_code,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"설정 오류: {str(e)}"
        )
    except MakeshopAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Makeshop API 오류: [{e.return_code}] {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Makeshop API 테스트 실패: {str(e)}"
        )


@app.get("/test/outbound-ip", tags=["Tests"])
def test_outbound_ip():
    """
    Cloud Run의 아웃바운드 IP 주소를 확인합니다.
    
    Cloud NAT이 제대로 설정되어 있으면:
    - 응답 IP: 34.158.215.39 (고정 IP)
    
    NAT이 없으면:
    - 응답 IP: 동적 IP (매번 변함)
    
    Returns:
        아웃바운드 IP 주소 및 관련 정보
    """
    try:
        import requests
        import json
        
        results = {}
        
        # 1. ifconfig.me - 깨끗한 IP 반환
        try:
            response = requests.get("https://ifconfig.me", timeout=5)
            results["ifconfig_me"] = {
                "ip": response.text.strip() if response.status_code == 200 else None,
                "status_code": response.status_code
            }
        except Exception as e:
            results["ifconfig_me"] = {"error": str(e)}
        
        # 2. httpbin.org - JSON 형식 응답
        try:
            response = requests.get("https://httpbin.org/ip", timeout=5)
            if response.status_code == 200:
                data = response.json()
                results["httpbin_org"] = {
                    "ip": data.get("origin"),
                    "status_code": response.status_code
                }
            else:
                results["httpbin_org"] = {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            results["httpbin_org"] = {"error": str(e)}
        
        # 3. myip.dnsomatic.com - DNS 오버 IP (다른 프로토콜 테스트)
        try:
            response = requests.get("https://myip.dnsomatic.com", timeout=5)
            results["dnsomatic"] = {
                "ip": response.text.strip() if response.status_code == 200 else None,
                "status_code": response.status_code
            }
        except Exception as e:
            results["dnsomatic"] = {"error": str(e)}
        
        # 4. Makeshop API 호출 시 보이는 IP 확인 (JSON 형식)
        makeshop_test_result = None
        try:
            response = requests.get("https://httpbin.org/user-agent", timeout=5)
            if response.status_code == 200:
                makeshop_test_result = response.json()
        except Exception as e:
            makeshop_test_result = {"error": str(e)}
        
        # 통합 결과
        primary_ip = None
        if results.get("ifconfig_me", {}).get("ip"):
            primary_ip = results["ifconfig_me"]["ip"]
        elif results.get("httpbin_org", {}).get("ip"):
            primary_ip = results["httpbin_org"]["ip"]
        
        is_nat_configured = primary_ip == "34.158.215.39" if primary_ip else False
        
        return {
            "status": "success",
            "message": "아웃바운드 IP 확인 완료",
            "primary_outbound_ip": primary_ip,
            "expected_nat_ip": "34.158.215.39",
            "nat_configured": is_nat_configured,
            "nat_status": "✅ Cloud NAT 정상 작동" if is_nat_configured else "⚠️ Cloud NAT 미설정 또는 보류 중",
            "results": results,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"아웃바운드 IP 확인 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"아웃바운드 IP 확인 실패: {str(e)}"
        )

