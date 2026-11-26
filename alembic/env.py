"""
Alembic environment configuration
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
import os
import sys

from dotenv import load_dotenv
from urllib.parse import quote

# Ensure app module is in the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables (.env 경로 명시)
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

# Import models after path is set
from app.models import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Try to get SQLALCHEMY_DATABASE_URL first, otherwise construct from individual env vars
    sqlalchemy_url = os.getenv("SQLALCHEMY_DATABASE_URL")
    
    if not sqlalchemy_url:
        # Construct database URL from individual environment variables
        db_user = os.getenv("DB_USER", "root")
        db_password = os.getenv("DB_PASSWORD", "")
        # Prefer DB_HOST; fallback to CLOUD_SQL_HOST for compatibility
        db_host = os.getenv("DB_HOST") or os.getenv("CLOUD_SQL_HOST", "127.0.0.1")
        db_port = os.getenv("DB_PORT", "3306")
        db_name = os.getenv("DB_NAME", "babba")

        # 필수 환경변수 점검 (DB_PORT는 기본값 있으므로 제외)
        missing_vars = []
        for var, val in [
            ("DB_USER", db_user),
            ("DB_PASSWORD", db_password),
            ("DB_HOST", db_host),
            ("DB_NAME", db_name)
        ]:
            if val == "" or val is None:
                missing_vars.append(var)
        if missing_vars:
            print(f"[ERROR] 다음 환경변수가 비어 있습니다: {', '.join(missing_vars)}")
            print(".env 파일을 확인하거나, 환경변수를 올바르게 설정하세요.")
            sys.exit(1)

        # URL-encode credentials to safely handle special characters like '@' or '!'
        db_user_enc = quote(db_user, safe="")
        db_password_enc = quote(db_password, safe="")

        # Unix socket 사용 여부 확인
        if db_host.startswith("/cloudsql/"):
            # Unix socket 연결 (Cloud SQL)
            sqlalchemy_url = f"mysql+pymysql://{db_user_enc}:{db_password_enc}@/{db_name}?unix_socket={db_host}"
        else:
            # TCP 연결
            sqlalchemy_url = f"mysql+pymysql://{db_user_enc}:{db_password_enc}@{db_host}:{db_port}/{db_name}"

    context.configure(
        url=sqlalchemy_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Try to get SQLALCHEMY_DATABASE_URL first, otherwise construct from individual env vars
    sqlalchemy_url = os.getenv("SQLALCHEMY_DATABASE_URL")
    
    if not sqlalchemy_url:
        # Construct database URL from individual environment variables
        db_user = os.getenv("DB_USER", "root")
        db_password = os.getenv("DB_PASSWORD", "")
        db_host = os.getenv("DB_HOST") or os.getenv("CLOUD_SQL_HOST", "127.0.0.1")
        db_port = os.getenv("DB_PORT", "3306")
        db_name = os.getenv("DB_NAME", "babba")

        # 필수 환경변수 점검 (DB_PORT는 기본값 있으므로 제외)
        missing_vars = []
        for var, val in [
            ("DB_USER", db_user),
            ("DB_PASSWORD", db_password),
            ("DB_HOST", db_host),
            ("DB_NAME", db_name)
        ]:
            if val == "" or val is None:
                missing_vars.append(var)
        if missing_vars:
            print(f"[ERROR] 다음 환경변수가 비어 있습니다: {', '.join(missing_vars)}")
            print(".env 파일을 확인하거나, 환경변수를 올바르게 설정하세요.")
            sys.exit(1)

        # Debug output
        print("[DEBUG] Constructing database URL...")
        print(f"[DEBUG] DB_USER: {db_user}")
        print(f"[DEBUG] DB_HOST: {db_host}")
        print(f"[DEBUG] DB_PORT: {db_port}")
        print(f"[DEBUG] DB_NAME: {db_name}")

        # URL-encode credentials for special characters
        db_user_enc = quote(db_user, safe="")
        db_password_enc = quote(db_password, safe="")

        # Unix socket 사용 여부 확인
        if db_host.startswith("/cloudsql/"):
            # Unix socket 연결 (Cloud SQL)
            sqlalchemy_url = f"mysql+pymysql://{db_user_enc}:{db_password_enc}@/{db_name}?unix_socket={db_host}"
            print(f"[DEBUG] Using Unix socket: {db_host}")
        else:
            # TCP 연결
            sqlalchemy_url = f"mysql+pymysql://{db_user_enc}:{db_password_enc}@{db_host}:{db_port}/{db_name}"

    # redact encoded password for logging
    print(f"[DEBUG] Connection URL: {sqlalchemy_url.replace(db_password_enc, '****')}")

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = sqlalchemy_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
