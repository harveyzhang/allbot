#!/bin/sh
set -eu
cd /app
redis-server /app/redis.conf --bind 127.0.0.1 --protected-mode yes --dir /data/redis --daemonize yes
attempt=0
until redis-cli -h 127.0.0.1 ping | grep -qx PONG; do
    attempt=$((attempt + 1))
    [ "$attempt" -lt 20 ] || { echo "Redis startup timed out" >&2; exit 1; }
    sleep 0.25
done
exec python3 /app/main.py "$@"
