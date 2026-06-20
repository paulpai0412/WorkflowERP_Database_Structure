# Checkpoint Payload Schema

Checkpoint payload 用於在每個需要使用者確認的階段固定資料格式。

## 必填欄位

- `checkpoint_id`：唯一識別碼。
- `phase`：例如 `phase_4_sql_review`。
- `version`：payload 版本。
- `title`：繁體中文標題。
- `summary`：管理視角摘要。
- `technical_details`：技術視角明細。
- `requires_user_confirmation`：是否需要使用者批准。
- `confirmation_prompt`：要求使用者確認的文字。
- `validator_evidence`：validator 證據路徑與結果。
- `residual_risks`：仍存在的風險。

## 原則

Checkpoint 不得包含 DB credentials。SQL checkpoint 可包含 SQL 文字，但不得包含可由瀏覽器直接執行的連線資訊。
## Confirmation Identity Fields

Every checkpoint payload and confirmation must carry enough identity to prevent stale approvals:

- `run_id`: current harness run id.
- `checkpoint_id`: current checkpoint id.
- `payload_hash`: hash of the current checkpoint payload.
- `confirmation_id`: unique id generated when the user confirms or requests changes.
- `selectedOptions.changeScope`: optional repair scope such as source logic, formula logic, SQL conditions, data result, HTML design, Excel design, visual style, or delivery.

The harness must reject a confirmation when `run_id`, `checkpoint_id`, or `payload_hash` does not match the current checkpoint.
