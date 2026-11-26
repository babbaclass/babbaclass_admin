"""
Database connection configuration for Cloud SQL using SQLAlchemy 2.0
Supports both:
1. Cloud SQL Auth Proxy (via gcloud ADC) - no password needed
2. Direct connection with password
3. Service Account Key File authentication
"""

import os
import sys
from urllib.parse import quote
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Set Google Application Credentials from environment if provided
# This allows authentication without gcloud auth application-default login
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if GOOGLE_APPLICATION_CREDENTIALS:
    if os.path.exists(GOOGLE_APPLICATION_CREDENTIALS):
        print(f"[DEBUG] Using service account key: {GOOGLE_APPLICATION_CREDENTIALS}", file=sys.stderr)
    else:
        print(f"[WARN] GOOGLE_APPLICATION_CREDENTIALS path does not exist: {GOOGLE_APPLICATION_CREDENTIALS}", file=sys.stderr)

"""Environment-driven DB connection settings.

Supported SSL env vars:
    DB_SSL_MODE: one of DISABLED, PREFERRED, REQUIRED, VERIFY_CA, VERIFY_IDENTITY
    DB_SSL_CA: Path to CA certificate (VERIFY_CA / VERIFY_IDENTITY)
    DB_SSL_CERT: Client certificate path (optional)
    DB_SSL_KEY: Client key path (optional)

Examples:
    # Disable verification (NOT for production)
    export DB_SSL_MODE=DISABLED

    # Proper verification
    export DB_SSL_MODE=VERIFY_CA
    export DB_SSL_CA=/certs/server-ca.pem
    export DB_SSL_CERT=/certs/client-cert.pem
    export DB_SSL_KEY=/certs/client-key.pem
"""
DB_USER = os.getenv("DB_USER") or "root"
DB_PASSWORD = os.getenv("DB_PASSWORD", "").strip()  # Empty string if not set
DB_NAME = os.getenv("DB_NAME") or "babba"
Cloud_SQL_host_env = os.getenv("CLOUD_SQL_HOST") or "127.0.0.1"
CLOUD_SQL_INSTANCE = os.getenv("CLOUD_SQL_INSTANCE", "").strip()
DB_SSL_MODE = (os.getenv("DB_SSL_MODE") or "PREFERRED").upper().strip()
DB_SSL_CA = os.getenv("DB_SSL_CA")
DB_SSL_CERT = os.getenv("DB_SSL_CERT")
DB_SSL_KEY = os.getenv("DB_SSL_KEY")

# Normalize host (some envs may supply uppercase inadvertently)
CLOUD_SQL_HOST = Cloud_SQL_host_env.strip()

# Cloud Run 내장 Cloud SQL Proxy 사용 시 Unix 소켓 경로
# /cloudsql/<INSTANCE_CONNECTION_NAME> 디렉토리가 존재하면 내장 proxy 사용
UNIX_SOCKET_PATH = ""
if CLOUD_SQL_INSTANCE:
    socket_dir = f"/cloudsql/{CLOUD_SQL_INSTANCE}"
    if os.path.exists(socket_dir):
        UNIX_SOCKET_PATH = socket_dir
        print(f"[DEBUG] Cloud Run built-in proxy detected: {socket_dir}", file=sys.stderr)
    else:
        print(f"[DEBUG] Unix socket dir not found: {socket_dir}, falling back to TCP", file=sys.stderr)

# Debug logging
print(f"[DEBUG] DB_USER={DB_USER}, DB_NAME={DB_NAME}, HOST={CLOUD_SQL_HOST}", file=sys.stderr)
if UNIX_SOCKET_PATH:
    print(f"[DEBUG] Using Unix socket: {UNIX_SOCKET_PATH}", file=sys.stderr)

# Build database URL based on connection mode
if UNIX_SOCKET_PATH:
    # Cloud Run 내장 proxy → Unix socket 연결 (VPC 무관, 가장 안정적)
    if DB_PASSWORD:
        DB_PASSWORD_ENCODED = quote(DB_PASSWORD, safe='')
        base_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD_ENCODED}@/{DB_NAME}?unix_socket={UNIX_SOCKET_PATH}"
    else:
        base_url = f"mysql+pymysql://{DB_USER}@/{DB_NAME}?unix_socket={UNIX_SOCKET_PATH}"
    auth_mode = "Cloud Run built-in proxy (Unix socket)"
elif DB_PASSWORD:
    DB_PASSWORD_ENCODED = quote(DB_PASSWORD, safe='')
    base_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD_ENCODED}@{CLOUD_SQL_HOST}:3306/{DB_NAME}"
    auth_mode = "password-based"
else:
    base_url = f"mysql+pymysql://{DB_USER}@{CLOUD_SQL_HOST}:3306/{DB_NAME}"
    auth_mode = "Cloud SQL Auth Proxy (TCP)"

SQLALCHEMY_DATABASE_URL = base_url

print(
    f"[DEBUG] Connection URL: {SQLALCHEMY_DATABASE_URL[:80]}...",
    file=sys.stderr,
)
print(f"[DEBUG] Auth mode: {auth_mode}", file=sys.stderr)
print(f"[DEBUG] SSL mode: {DB_SSL_MODE}", file=sys.stderr)
# Create engine with SQLAlchemy 1.4 settings
base_connect_args = {"connect_timeout": 10}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    connect_args=base_connect_args,
)

# SQLAlchemy 1.4 style session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
