# Jarvis Runtime

## 目的

Jarvis Runtimeは、Jarvis CoreまたはAI Agentが選択したToolを安全に扱うための実行境界である。

JarvisはToolを直接実行せず、Runtimeを通してTool定義の取得、入力検証、実行前確認、実行、監査記録へ進む設計にする。

Runtime v0.1では、実Tool実行ではなくTool Registryを使った検証とstub executionまでを実装している。
Executor Registry v0.1では、Runtime本体からToolごとの実行処理を分離し、実行先をRegistry経由で選ぶ構造を追加している。
Confirmation Engine v0.1では、Tool定義の `risk_level` と `confirmation_required` を見て、実行前に確認が必要かを判定する。

---

## 実装状態

Implemented (v0.1):

* `get_tool`
* `validate`
* `dry_run`
* `execute_stub`
* `ExecutorRegistry`
* `ConfirmationEngine`

Not Yet Implemented:

* Permission
* Confirmation UI
* Real Tool Execution

`execute_stub` はToolの実処理を呼び出さない。確認が不要、または確認済みで、入力検証に成功した場合、`ExecutorRegistry` から取得した `StubExecutor` を呼び、`execution_mode: "stub"` とstub結果を返す。

---

## Runtime API

現在利用可能なAPI:

* `GET /api/runtime/tool/{tool_id}`
* `POST /api/runtime/validate`
* `POST /api/runtime/dry-run`
* `POST /api/runtime/execute`
* `GET /api/audit`

リクエスト形式:

```json
{
  "tool_id": "garden.add_task",
  "params": {
    "title": "water plants"
  },
  "confirmed": false
}
```

`confirmed` は任意である。未指定の場合は `false` として扱う。

`GET /api/runtime/tool/{tool_id}` は対象ToolのRuntime summaryを返す。

返す主な情報:

* `id`
* `skill_id`
* `mode`
* `risk_level`
* `confirmation_required`
* `audit_required`

`POST /api/runtime/validate` はToolの `input_schema.required` に基づいて必須入力を検証する。

`POST /api/runtime/dry-run` は検証結果に加えて、実行した場合に使われるTool情報、リスク、確認要否、監査要否を返す。

`POST /api/runtime/execute` はRuntime v0.1ではstub実行であり、Real Tool Executionではない。

確認が必要なToolに `confirmed: false` または未指定で `POST /api/runtime/execute` した場合、Runtimeは実行せず、Executorも呼ばない。

`GET /api/audit` はAudit Log v0.1の最近の記録を返す。クエリ `limit` は任意で、デフォルトは50件。返却順は新しい記録が先である。

---

## 現在の実行フロー

Runtime v0.1の実行フロー:

```text
Jarvis Core / API Client
↓
Runtime
↓
Tool Registry
↓
Tool Definition
↓
Confirmation Engine
↓
Input Validation
↓
Dry Run or Executor Registry
↓
StubExecutor
↓
Result
```

現在のRuntimeは、Tool Registry配下のJSON定義を読み取り、Tool IDに一致する定義を探す。

Tool定義が存在しない場合は404を返す。

Tool定義が壊れている場合は500を返す。

---

## Executor Registry

Executor Registry v0.1は `backend/executors.py` に実装している。

構成:

* `BaseExecutor`: executor共通インターフェース。`execute(tool, params)` を持つ。
* `StubExecutor`: 実Tool実行を行わず、stub結果を返す。
* `ExecutorRegistry`: `tool_id` または `skill_id` からexecutorを取得する。

現在は全Toolが `StubExecutor` を使う。Weather API、Travel DB、Developer実処理、Home Assistant、OpenAI API、MCPなどの実行は行わない。

Runtimeは `execute_stub` 内で `ExecutorRegistry.get_executor(tool.id, tool.skill_id)` を呼び、返されたexecutorに実行を委譲する。Runtime本体には `if tool_id == ...` のようなTool別分岐を置かない。

現在のstub返却例:

```json
{
  "message": "stub execution",
  "tool_id": "get_forecast"
}
```

将来的には、`ExecutorRegistry` に以下のようなexecutorを `tool_id` または `skill_id` 単位で登録する。

* `WeatherExecutor`
* `TravelExecutor`
* `DeveloperExecutor`
* `HomeExecutor`

Real Tool Executionへ進む前に、executorごとのRisk、Audit、Permission、Confirmationとの接続を追加する。

---

## Tool Registryとの関係

RuntimeはTool Registryを実行時の正とする。

Tool定義から参照する主な項目:

* `id`
* `skill_id`
* `mode`
* `risk_level`
* `confirmation_required`
* `audit_required`
* `input_schema`

`confirmation_required` がTool定義にない場合、Runtimeは `risk_level: high` を確認必須として扱う。

`audit_required` がTool定義にない場合、Runtimeは `risk_level: medium / high` または `mode: write / mixed` を監査対象として扱う。

---

## Permission

Permissionは未実装である。

将来的には、Runtimeが以下を確認してから実行へ進む。

* user
* role
* target data
* required permission
* privacy level
* risk level

コード変更、家電操作、デプロイなど現実世界に影響する操作は、強い権限を必要とする。

---

## Confirmation

Confirmation Engine v0.1は `backend/confirmation.py` に実装している。

構成:

* `ConfirmationDecision`: 確認要否、実行許可、理由を表す。
* `ConfirmationEngine`: Tool定義の `risk_level` と `confirmation_required` から実行前確認が必要か判定する。

現在のConfirmation v0.1:

* UIなし
* `confirmed` フラグのみ
* `risk_level: high` または `confirmation_required: true` をブロック
* `confirmed: true` の場合のみ確認必須Toolのstub実行を許可
* Real Tool Executionなし
* `execute` はまだstub

確認不要Toolの返却例:

```json
{
  "success": true,
  "tool_id": "get_forecast",
  "execution_mode": "stub",
  "result": {
    "message": "stub execution",
    "tool_id": "get_forecast"
  },
  "blocked": false,
  "confirmation_required": false,
  "confirmed": false,
  "reason": null,
  "errors": []
}
```

確認必要Toolが未確認でブロックされた場合の返却例:

```json
{
  "success": false,
  "tool_id": "restart_service",
  "execution_mode": null,
  "result": null,
  "blocked": true,
  "confirmation_required": true,
  "confirmed": false,
  "reason": "confirmation required before execution",
  "errors": []
}
```

この場合、`ExecutorRegistry.get_executor(...)` と executor の `execute(...)` は呼ばない。

将来的には、Runtimeがリスクのある操作について人間の確認を要求する。

確認時に伝える情報:

* 何を実行するか
* なぜ実行するか
* どのToolを使うか
* どのデータに影響するか
* リスクレベル
* 取り消し可能か

初期方針は `Level 0: 提案だけ` から `Level 1: 確認して実行` を基本とする。

将来拡張:

* 確認リクエストID
* UIでの承認
* 承認期限
* user / session / request_id
* family role / permission との連携
* Audit Logとの詳細連携

---

## Audit Log

Audit Log v0.1は、Runtime経由のstub実行記録とconfirmation block記録を `logs/audit.log` にJSONL形式で1行ずつ追記する。

現在のAudit Log v0.1:

* JSONL保存
* `execute_stub` と `confirmation_blocked` を記録
* executor実行結果ではなくRuntimeの実行イベントを記録
* UIなし
* DBなし
* 権限管理なし

1行の主な項目:

* `timestamp`
* `event_type`
* `tool_id`
* `skill_id`
* `execution_mode`
* `status`
* `risk_level`
* `confirmation_required`
* `confirmed`
* `audit_required`
* `reason`
* `error`

失敗時は可能な範囲で `status: "failed"` と `error` を記録する。

確認でブロックした場合は `event_type: "runtime.confirmation_blocked"`、`status: "blocked"`、`confirmation_required`、`confirmed`、`reason` を記録する。

将来拡張予定:

* `validate` / `dry_run` / real execution も記録
* user / session / request_id の記録
* SQLite化
* UIでの閲覧
* 検索/フィルタ
* Confirmation結果との接続
* Permission判定との接続

---

## 重要な考え

RuntimeはAIの自由を制限するためだけの仕組みではない。

AIが家族から信頼され、将来より多くのことを任されるための土台である。

Jarvisは、

* 何ができるか
* なぜ実行したか
* 誰が許可したか
* 何が起きたか

を説明できる必要がある。

Runtimeはその説明責任を支える。
