# E2E Expense Analysis

本 skill 的費用分析 E2E 必須執行真實資料庫查詢，不可用 fake、mock 或 smoke test 取代。

## 執行順序

1. 先跑 SQLite first-pass：

```bash
bash scripts/run_expense_analysis_sqlite_e2e.sh
```

預期輸出：

```text
sqlite_expense_e2e=pass row_count=6 total_amount=120000 total_budget=100000 variance_amount=20000 max_expense_ratio=0.35
```

2. 再跑 Docker PostgreSQL formal substitute：

```bash
bash scripts/run_expense_analysis_postgres_e2e.sh
```

預期輸出包含 SQLite pass line，並以 PostgreSQL pass line 結束：

```text
postgres_expense_e2e=pass row_count=6 total_amount=120000 total_budget=100000 variance_amount=20000 max_expense_ratio=0.35
```

## Fixture Rows

固定 8 筆來源資料：

| 年度 | 部門 | 費用科目 | 金額 | 預算 |
| --- | --- | --- | ---: | ---: |
| 2026 | 行政部 | 旅費 | 35000 | 30000 |
| 2026 | 行政部 | 文具 | 10000 | 8000 |
| 2026 | 研發部 | 雲端服務 | 30000 | 25000 |
| 2026 | 研發部 | 軟體訂閱 | 25000 | 22000 |
| 2026 | 業務部 | 交際費 | 12000 | 10000 |
| 2026 | 業務部 | 廣告費 | 8000 | 5000 |
| 2025 | 行政部 | 旅費 | 9000 | 9000 |
| 2026 | 行政部 | 資產購置 | 50000 | 50000 |

SQL 必須只納入 `year = 2026` 且 `account_type = expense` 的資料，因此包含 6 筆，排除 1 筆非 2026 資料與 1 筆非費用科目資料。

## 量化驗收

- `row_count == 6`
- `columns == ["department_code", "department_name", "expense_subject", "amount", "budget_amount", "variance_amount", "expense_ratio"]`
- `aggregates.total_amount == 120000`
- `aggregates.total_budget == 100000`
- `aggregates.variance_amount == 20000`
- `aggregates.max_expense_ratio == 0.35`
- `excluded_rows.non_2026 == 1`
- `excluded_rows.non_expense_account == 1`
- `sql_safety.readonly is True`
- `sql_safety.blocked_keywords == []`

## 證據要求

交付前需提供：

- SQLite script pass line。
- PostgreSQL script pass line，或 Docker/sandbox 阻擋時的完整錯誤。
- `pytest tests/skill_scripts/test_expense_analysis_sqlite_e2e.py tests/skill_scripts/test_expense_analysis_postgres_e2e.py -v` 結果。
