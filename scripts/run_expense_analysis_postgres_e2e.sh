#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="test_db/docker-compose.postgres-e2e.yml"
CONTAINER="wferp-postgres-e2e"
PROMPT="請產出2026第一季費用分析，依部門與會計科目彙總未稅金額、稅額、總額與占比"

echo "Step 1/2: run local SQLite E2E before PostgreSQL MSSQL simulation"
bash scripts/run_expense_analysis_sqlite_e2e.sh

echo "Step 2/2: run PostgreSQL E2E as formal MSSQL DB simulation"
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
        -v "${PWD}/test_db/postgres_e2e:/init:ro" \
        -d postgres:16 >/dev/null
fi

for _ in $(seq 1 30); do
    if docker exec "${CONTAINER}" pg_isready -U wferp -d wferp_e2e >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

docker exec -i "${CONTAINER}" psql -U wferp -d wferp_e2e -f /init/01_create_expense_fixture.sql

echo "PostgreSQL fixture counts:"
docker exec -i "${CONTAINER}" psql -U wferp -d wferp_e2e -c 'SELECT COUNT(*) AS acpta_count FROM dbo."ACPTA";'
docker exec -i "${CONTAINER}" psql -U wferp -d wferp_e2e -c 'SELECT COUNT(*) AS acptb_count FROM dbo."ACPTB";'
docker exec -i "${CONTAINER}" psql -U wferp -d wferp_e2e -c 'SELECT SUM("TB017") AS included_untaxed, SUM("TB018") AS included_tax, SUM("TB017" + "TB018") AS included_total FROM dbo."ACPTA" header JOIN dbo."ACPTB" detail ON header."TA001" = detail."TB001" AND header."TA002" = detail."TB002" WHERE header."TA003" >= '"'"'20260101'"'"' AND header."TA003" <= '"'"'20260331'"'"' AND COALESCE(header."TA018", '"'"''"'"') <> '"'"'Y'"'"' AND header."TA024" = '"'"'Y'"'"';'
docker exec -i "${CONTAINER}" psql -U wferp -d wferp_e2e -c 'SELECT SUM("TB017" + "TB018") AS excluded_total FROM dbo."ACPTA" header JOIN dbo."ACPTB" detail ON header."TA001" = detail."TB001" AND header."TA002" = detail."TB002" WHERE header."TA003" < '"'"'20260101'"'"' OR header."TA003" > '"'"'20260331'"'"' OR header."TA024" <> '"'"'Y'"'"' OR COALESCE(header."TA018", '"'"''"'"') = '"'"'Y'"'"';'

echo "Generated SQL:"
python3 -m tests.skill_scripts.expense_report_fixture

export WFERP_RUN_POSTGRES_E2E=1
export WFERP_POSTGRES_E2E_CONTAINER="${CONTAINER}"
export WFERP_POSTGRES_E2E_DSN="postgresql://wferp:wferp_pass@127.0.0.1:55432/wferp_e2e"

pytest tests/skill_scripts/test_expense_analysis_postgres_e2e.py -v
