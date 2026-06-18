#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="test_db/docker-compose.postgres-e2e.yml"
CONTAINER="wferp-postgres-e2e"

bash scripts/run_expense_analysis_sqlite_e2e.sh

if docker compose version >/dev/null 2>&1; then
    docker compose -f "${COMPOSE_FILE}" up -d
elif docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER}"; then
    docker start "${CONTAINER}" >/dev/null
else
    docker run \
        --name "${CONTAINER}" \
        -e POSTGRES_DB=wferp_e2e \
        -e POSTGRES_USER=wferp \
        -e POSTGRES_PASSWORD=wferp_pass \
        -p 55432:5432 \
        -d postgres:16 >/dev/null
fi

for _ in $(seq 1 30); do
    if docker exec "${CONTAINER}" pg_isready -U wferp -d wferp_e2e >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

python3 -m tests.skill_scripts.expense_report_fixture --postgres-seed-sql \
    | docker exec -i "${CONTAINER}" psql -U wferp -d wferp_e2e >/dev/null

python3 -m tests.skill_scripts.expense_report_fixture --postgres-e2e --container "${CONTAINER}"
