#!/bin/sh
# Smoke test of the container setup: build the image, start PostgreSQL, run the migrations,
# start the backend, then check that it is healthy, does not run as root, and records a demo
# request. Uses a separate Compose project so it never touches the normal local stack.
# Run from anywhere: `make docker-smoke` (from backend/) or in CI.
set -eu

repo_root=$(cd "$(dirname "$0")/../.." && pwd)
port=${SMOKE_PORT:-8099}
project=performance-dashboard-smoke

compose() {
    BACKEND_PORT="$port" docker compose --project-directory "$repo_root" \
        --file "$repo_root/compose.yaml" --project-name "$project" "$@"
}

fail() {
    printf 'Smoke test failed: %s\n' "$1" >&2
    compose logs --no-color >&2 || true
    exit 1
}

# Always remove the containers and the throwaway database volume.
trap 'compose down --volumes --remove-orphans >/dev/null 2>&1 || true' EXIT

compose up --build --detach --wait --wait-timeout 120 || fail "the stack did not become healthy"

base="http://127.0.0.1:$port"

health=$(curl --fail --silent --show-error "$base/health") || fail "/health did not answer 200"
[ "$health" = '{"status":"ok","database":"ok"}' ] || fail "unexpected /health body: $health"

uid=$(compose exec -T backend id -u) || fail "could not run id in the container"
[ "$uid" != 0 ] || fail "the backend runs as root"

# Any status counts here: simulated failures are recorded too.
curl --silent --output /dev/null "$base/demo/users" || fail "/demo/users did not answer"
total=$(curl --fail --silent --show-error "$base/metrics" |
    python3 -c 'import json, sys; print(json.load(sys.stdin)["summary"]["total_requests"])') ||
    fail "/metrics did not answer 200"
[ "$total" = 1 ] || fail "expected 1 recorded request, /metrics reports $total"

printf 'Smoke test passed: healthy, uid %s, migrations applied, 1 request recorded.\n' "$uid"
