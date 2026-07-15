#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! python -c "
import psycopg2
import os
try:
    psycopg2.connect(os.environ['DATABASE_URL'])
    print('PostgreSQL is ready.')
except Exception:
    exit(1)
" 2>/dev/null; do
    sleep 2
done

exec "$@"
