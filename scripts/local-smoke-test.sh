#!/usr/bin/env bash
# Build, start, and smoke-test the lab via docker compose.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Building and starting (compose + override)…"
docker compose up --build -d

cleanup() { echo "==> Tearing down…"; docker compose down -v; }
trap cleanup EXIT

echo "==> Waiting for /health…"
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
    echo "   healthy"
    break
  fi
  sleep 1
  [ "$i" -eq 30 ] && { echo "   health check timed out"; exit 1; }
done

echo "==> Checking readiness (ground truth loaded)…"
curl -fsS http://127.0.0.1:8080/readyz | grep -Eq '"ready":[[:space:]]*true' || {
  echo "   FAIL: not ready"; exit 1; }
echo "   ok"

echo "==> Checking meta/events leak no answer key…"
if curl -fsS http://127.0.0.1:8080/api/meta | grep -qi "/var/log/auth.log\|expected"; then
  echo "   FAIL: answer key leaked via /api/meta"; exit 1
fi
echo "   ok"

echo "==> Submitting S1-T1 (/var/log/auth.log) …"
curl -fsS -X POST http://127.0.0.1:8080/api/tasks/S1-T1/submit \
  -H 'Content-Type: application/json' -d '{"answer":"/var/log/auth.log"}'
echo

echo "==> Submitting S2-T5 ordered timeline …"
curl -fsS -X POST http://127.0.0.1:8080/api/tasks/S2-T5/submit \
  -H 'Content-Type: application/json' \
  -d '{"answer":{"order":["EVT-0009","EVT-0018","EVT-0019"]}}'
echo

echo "==> Smoke test passed."
