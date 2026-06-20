# wferp-report

## 13-Phase Engine, 4-Step Visual Companion

The technical harness still has 13 phases. The user-facing Visual Companion is simplified to 4 steps only:

1. Source-to-Output Logic
2. SQL Query
3. Data Result and Report Design
4. Final Delivery

This simplification is UI-only. It does not remove SQL safety, SQLite enrichment, lookup tables, validators, repair flow, state gates, Visual Companion confirmation/modify controls, or delivery evidence.

## True Excel Output

When Excel output is requested, generate a real `.xlsx` workbook and evidence. Use the spreadsheets skill and `@oai/artifact-tool`; do not default to `openpyxl`. The workbook export must update `state.json` with `final_xlsx_path` and `excel_workbook_evidence`.

`wferp-report` 是 Workflow ERP / WFERP 的 LLM-driven report harness。它把使用者 prompt、uploaded files、Excel 欄位與公式、WFERP schema/relationship、read-only SQL、DB execution、SQLite enrichment、data preview、report type/design/options、React renderer、single-file HTML 與 subagent validator evidence 串成一條可驗證流程。

執行本 skill 就是執行 harness flow。不要只產出一段 SQL 後停止；必須建立 run、產生 checkpoint、等待 user confirmation、保存資料預覽與 validator evidence，最後才 delivery。

## 輸入組合

四種輸入組合都支援，且全部收斂成同一份 `plan/normalized-report-plan.json`：

1. prompt 資料來源 + prompt 報表格式。
2. prompt 資料來源 + Excel report template。
3. Excel source + prompt 報表格式。
4. Excel source + Excel report template。

Excel 可能包含 DB 欄位、lookup 對照、公式欄位、舊報表模板、人工欄位與格式欄位。Skill 需由 LLM 判斷欄位與公式語意，不要求使用者手動標註。

## Phase Flow

1. Phase 0：Intake。
2. Phase 1：Source / Excel Requirement。
3. Phase 2：Report Planning。
4. Phase 3：Field & Formula Checkpoint。
5. Phase 4：SQL Review Checkpoint。
6. Phase 5：Confirmed DB Execution。
7. Phase 6：Data Preview Checkpoint。
8. Phase 7：Report Selection Checkpoint。
9. Phase 8：Final Report Scaffold。
10. Phase 9：Section Build。
11. Phase 10：Final Review。
12. Phase 11：Repair。
13. Phase 12：Delivery。

## 使用者 Checkpoints

主要 checkpoint 收斂成四個，避免每個內部小步驟都打斷使用者：

- **Field & Formula Checkpoint**：確認 uploaded files、Excel confirmation、sheet roles、DB-backed / formula-backed / lookup-backed / manual-only 欄位、WFERP schema/relationship mapping、report logic、chart/layout 初稿。
- **SQL Review Checkpoint**：確認 read-only SQL、table/field readable names、joins、filters、aggregates、assumptions 與不下推 DB 的公式/enrichment 欄位。
- **Data Preview Checkpoint**：確認 DB raw data preview、SQLite enrichment、lookup hit/miss、formula status、aggregate checks 與 excluded rows。
- **Report Selection / Final Checkpoint**：確認 report type、design/options、chart/table/layout、React HTML report、Excel-like view、validator evidence、residual risks 與 SQLite retention。

## CLI 入口

```bash
python3 -m skill_scripts.cli_report_harness create-run --run-root wferp-report-runs --run-id run-001 --prompt "查詢費用分析" --llm-provider codex
python3 -m skill_scripts.cli_report_harness classify-workbook --run-dir wferp-report-runs/run-001 --input-file requirement.xlsx --llm-provider codex
python3 -m skill_scripts.cli_report_harness write-sql-review --run-dir wferp-report-runs/run-001 --sql "SELECT ..."
python3 -m skill_scripts.cli_report_harness serve-checkpoint --run-dir wferp-report-runs/run-001 --host 127.0.0.1 --port 0
python3 -m skill_scripts.cli_report_harness wait-confirmation --run-dir wferp-report-runs/run-001 --checkpoint sql_review
python3 -m skill_scripts.cli_report_harness write-raw-table --run-dir wferp-report-runs/run-001 --rows query-result.json
python3 -m skill_scripts.cli_report_harness write-raw-preview --run-dir wferp-report-runs/run-001
python3 -m skill_scripts.cli_report_harness run-sqlite-enrichment --run-dir wferp-report-runs/run-001
python3 -m skill_scripts.cli_report_harness write-enriched-preview --run-dir wferp-report-runs/run-001
python3 -m skill_scripts.cli_report_harness write-report-selection --run-dir wferp-report-runs/run-001 --report-design financial-control --include-chart --include-table --include-analysis
python3 -m skill_scripts.cli_report_harness scaffold-report --run-dir wferp-report-runs/run-001
python3 -m skill_scripts.cli_report_harness generate-report-section --run-dir wferp-report-runs/run-001 --section-id 01-executive-summary --component-name ExecutiveSummary01Section --code-file /tmp/section.tsx
python3 -m skill_scripts.cli_report_harness validate-report-section --run-dir wferp-report-runs/run-001 --section-id 01-executive-summary
python3 -m skill_scripts.cli_report_harness write-report-draft --run-dir wferp-report-runs/run-001 --payload report-draft.json
python3 -m skill_scripts.cli_report_harness write-final-review --run-dir wferp-report-runs/run-001 --payload final-review.json
python3 -m skill_scripts.cli_report_harness can-deliver --run-dir wferp-report-runs/run-001
```

`confirm` 可保存 `selectedOptions`。final review 若有 residual risks，必須用 `--accepted-residual-risk "validator_role: risk text"` 明確接受，否則 `can-deliver` 會阻擋交付。

複雜報表允許 LLM 依需求產生 section TSX，但必須經由 `generate-report-section` 或 `repair-report-section` 寫入單一 run-scoped section，並在每次寫入後執行 `validate-report-section`。Section 只能讀 embedded payload，不得連 DB、不得執行 SQL、不得發 network request、不得讀 credentials。

## 驗證

```bash
bash /home/timmypai/.codex/skills/wferp-report/scripts/validate-skill.sh
```

## Windows

若在 Windows 看到中文亂碼，請先看 `WINDOWS_ENCODING.md`。本 skill 固定使用 UTF-8；`SKILL.md` 與 JSON 不可轉成 UTF-8 BOM、Big5、CP950、ANSI 或 UTF-16。
