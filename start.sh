#!/bin/sh
set -e
cd /app
PORT="${PORT:-8080}"

mkdir -p /data 2>/dev/null || true

if [ -d /data ] && [ -w /data ]; then
  if [ ! -f /data/accounts.db ] && [ -f /app/data/accounts.db ]; then
    echo "Copying website data from /app/data to /data"
    cp -a /app/data/. /data/ || true
  fi
  if [ ! -f /data/coupons.json ] && [ -f /app/data/coupons.json ]; then
    cp -a /app/data/coupons.json /data/coupons.json || true
  fi
  if [ -z "$PYCLIPS_DATA_DIR" ]; then
    PYCLIPS_DATA_DIR=/data
  fi
  export PYCLIPS_DATA_DIR
fi

echo "PyClips website listening on 0.0.0.0:${PORT}"
echo "PyClips data dir: ${PYCLIPS_DATA_DIR:-/app/data}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips='*'
