#!/bin/bash

set -e

if [ -z "$CLOUD_SQL_INSTANCE" ]; then
  echo "ERROR: CLOUD_SQL_INSTANCE environment variable not set"
  exit 1
fi

echo "Starting Cloud SQL Auth Proxy for $CLOUD_SQL_INSTANCE on port 3306"
/cloud-sql-proxy -instances=$CLOUD_SQL_INSTANCE=tcp:127.0.0.1:3306 &
PROXY_PID=$!

echo "Waiting for Cloud SQL Proxy to be ready..."
for i in {1..30}; do
  if nc -z 127.0.0.1 3306 2>/dev/null; then
    echo "✓ Cloud SQL Proxy is ready on port 3306"
    break
  fi
  echo "  Attempt $i/30 - waiting for port 3306..."
  sleep 1
done

# Additional wait to ensure full initialization
sleep 2

echo "Running Alembic migrations..."
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_NAME=${DB_NAME:-babba}
export DB_USER=${DB_USER:-root}
export DB_PASSWORD=${DB_PASSWORD:-}

# Fix the alembic_version table if needed (from corrupted 044_order_item_settlement)
echo "[INFO] Checking and fixing alembic_version if needed..."
mysql -h $DB_HOST -P $DB_PORT -u $DB_USER ${DB_PASSWORD:+-p$DB_PASSWORD} $DB_NAME -e "UPDATE alembic_version SET version_num = '041' WHERE version_num LIKE '044%' OR version_num LIKE '043%' OR version_num LIKE '042%';" 2>/dev/null || true

echo "[INFO] Starting migration: alembic upgrade head"
alembic upgrade head
MIGRATION_RESULT=$?

if [ $MIGRATION_RESULT -eq 0 ]; then
  echo "✓ Database migrations completed successfully"
  exit 0
else
  echo "✗ Database migrations failed with exit code $MIGRATION_RESULT"
  exit 1
fi

trap "kill $PROXY_PID" EXIT
