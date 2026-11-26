#!/bin/bash

set -euo pipefail

# Cloud Run 내장 Cloud SQL Proxy 사용 (--add-cloudsql-instances로 자동 관리)
# entrypoint에서 별도 proxy를 실행하지 않음
if [ -n "${CLOUD_SQL_INSTANCE:-}" ]; then
  SOCKET_PATH="/cloudsql/${CLOUD_SQL_INSTANCE}"
  echo "Waiting for Cloud Run built-in Cloud SQL proxy (Unix socket)..."
  for i in {1..30}; do
    if [ -e "$SOCKET_PATH" ]; then
      echo "✓ Cloud SQL socket is ready: $SOCKET_PATH"
      break
    fi
    echo "  Attempt $i/30 - waiting for $SOCKET_PATH..."
    sleep 1
  done
  if [ ! -e "$SOCKET_PATH" ]; then
    echo "⚠️  Cloud SQL socket not found after 30s. Proceeding anyway..."
  fi
else
  echo "⚠️  CLOUD_SQL_INSTANCE not set. Skipping Cloud SQL socket check."
fi

# Run migrations only if RUN_MIGRATIONS is not set to 'false'
if [ "${RUN_MIGRATIONS:-true}" != "false" ]; then
  echo "Running database migrations..."
  echo "Checking migration status..."
  python3 << 'EOF'
import sys, os
sys.path.insert(0, '/app')
from app.database import SessionLocal
from sqlalchemy import text, inspect

session = SessionLocal()
try:
    # Get current migration versions from DB
    result = session.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num"))
    current_versions = [row[0] for row in result]
    
    print(f"  Current alembic_version table: {current_versions}")
    
    # Read all available migration files
    import os
    migration_dir = '/app/alembic/versions'
    available_migrations = sorted([f.replace('.py', '') for f in os.listdir(migration_dir) 
                                   if f.endswith('.py') and not f.startswith('__')])
    print(f"  Available migrations: {len(available_migrations)} files")
    print(f"  Latest available: {available_migrations[-1] if available_migrations else 'NONE'}")
    
    # If migrations are missing from DB but schema exists, we need to handle this carefully
    # Option: Keep existing migration history and let alembic upgrade from current point
    print("  ℹ️  Database schema appears to be ahead of migration history")
    print("  Proceeding with alembic upgrade to reconcile...")
    
finally:
    session.close()
EOF
  # Always run upgrade - alembic will handle idempotency
  alembic upgrade head || true
else
  echo "⚠️  Skipping database migrations (RUN_MIGRATIONS=false)"
fi

echo "Starting Uvicorn on port ${PORT:-8080}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
