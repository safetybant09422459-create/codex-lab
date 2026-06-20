# Jarvis Runtime

## 目的

Jarvis Runtimeは、Jarvis CoreまたはAI Agentが選択したToolを安全に扱うための実行境界である。

JarvisはToolを直接実行せず、Runtimeを通してTool定義の取得、入力検証、実行前確認、実行、監査記録へ進む設計にする。

Runtime v0.1では、Tool Registryを使った検証、Runtime safety layer経由の実行、Audit Log記録を実装している。
Executor Registry v0.1では、Runtime本体からToolごとの実行処理を分離し、実行先をRegistry経由で選ぶ構造を追加している。
Confirmation Engine v0.1では、Tool定義の `risk_level` と `confirmation_required` を見て、実行前に確認が必要かを判定する。
Permission Engine v0.1では、request body の `role` とTool定義の `skill_id` / `mode` / `risk_level` を見て、実行してよいかを判定する。
Weather Executor v0.1では、Weather Skillだけを deterministic な `local_weather_stub` としてRuntime safety layer経由で実行する。
Travel Runtime v0.1では、Travel Skillの読み取りToolを `local_travel_read` としてRuntime safety layer経由で実行し、`travel.create_trip` と `travel.create_timeline_item` をguarded writeとして実行する。

---

## 実装状態

Implemented (v0.1):

* `get_tool`
* `validate`
* `dry_run`
* `execute_stub`
* `ExecutorRegistry`
* `ConfirmationEngine`
* `PermissionEngine`
* `WeatherExecutor`
* `TravelExecutor`
* Travel Runtime v0.1
* `SQLiteTravelStorage` による `storage/travel.db` のlocal DB-backed read/write
* Travel guarded write tools: `travel.create_trip`, `travel.create_timeline_item`

Not Yet Implemented:

* Confirmation UI
* 外部APIを使うReal Tool Execution
* 追加Travel write tools

`execute_stub` は確認が不要、または確認済みで、入力検証に成功した場合、`ExecutorRegistry` から取得したexecutorを呼ぶ。Weather Skillは `WeatherExecutor` を呼び、`execution_mode: "local_weather_stub"` と副作用のないローカル結果を返す。Travel Skillの実装済みToolは `TravelExecutor` を呼び、読み取りでは `execution_mode: "local_travel_read"` とローカル読み取り結果を返し、guarded writeではRuntimeのPermission / Confirmation / Auditを通したうえで `SQLiteTravelStorage` へ保存する。その他の未実装Toolは `StubExecutor` を呼び、`execution_mode: "stub"` とstub結果を返す。

---

## Runtime API

現在利用可能なAPI:

* `GET /api/runtime/tool/{tool_id}`
* `POST /api/runtime/validate`
* `POST /api/runtime/dry-run`
* `POST /api/runtime/execute`
* `GET /api/audit`

Runtime/API検証コマンドは、プロジェクトルートの通常の `python` ではなく、仮想環境の `./.venv/bin/python` を前提にする。

```bash
cd /mnt/nas/projects/codex-lab
./.venv/bin/python scripts/check_runtime_api.py
```

この検証はFastAPIのASGI appでRuntime API相当の経路を呼び出す。Weatherは `local_weather_stub`、Travel readは `local_travel_read` として実行し、`restart_service` はRuntimeのstub実行として確認する。service restart APIは呼ばない。

リクエスト形式:

```json
{
  "tool_id": "garden.add_task",
  "params": {
    "title": "water plants"
  },
  "confirmed": false,
  "role": "guest"
}
```

`confirmed` は任意である。未指定の場合は `false` として扱う。
`role` は任意である。未指定の場合は `admin` ではなく `guest` として扱う。

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

`POST /api/runtime/execute` はRuntime v0.1の安全境界を通してexecutorを呼ぶ。Weather Skillは `WeatherExecutor` の `local_weather_stub`、Travel Skillの実装済み読み取りToolは `TravelExecutor` の `local_travel_read` を実行する。その他の未実装Toolは `StubExecutor` の `stub` 実行として扱う。

権限がないToolに `POST /api/runtime/execute` した場合、Runtimeは実行せず、Confirmation EngineもExecutorも呼ばない。

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
Input Validation
↓
Permission Engine
↓
Confirmation Engine
↓
Dry Run or Executor Registry
↓
WeatherExecutor / TravelExecutor / StubExecutor
↓
Result
```

現在のRuntimeは、Tool Registry配下のJSON定義を読み取り、Tool IDに一致する定義を探す。

Tool定義が存在しない場合は404を返す。

Tool定義が壊れている場合は500を返す。

### Tool JSON schemaの注意

Tool JSON の `input_schema.properties` では、各propertyに `type` が必要である。

今回の Runtime tools error では、`create_trip.json` の `prefectures` property に `type` が無く、Tool Registry読み込み時に `Invalid tool definition` になった。

影響:

* 1つのTool定義ミスで `/api/tools` が失敗する
* `/api/tools` に依存するWeb UIのTool一覧表示も壊れる

新Tool追加時の確認:

* `python -m json.tool` でJSON構文を確認する
* Runtime/APIで `/api/tools` が返ることも確認する

```bash
curl -s http://127.0.0.1:8001/api/tools | head -c 500
```

Jarvis Dev の systemd service 名は `jarvis-dev` である。

```bash
sudo systemctl restart jarvis-dev
```

注意:

* port `8000` は旧おでかけアプリ
* port `8001` が Jarvis Dev

---

## Executor Registry

Executor Registry v0.1は `backend/executors.py` に実装している。

構成:

* `BaseExecutor`: executor共通インターフェース。`execute(tool, params)` を持つ。
* `StubExecutor`: 実Tool実行を行わず、stub結果を返す。
* `ExecutorRegistry`: `tool_id` または `skill_id` からexecutorを取得する。

現在はWeather Skillが `WeatherExecutor`、Travel Skillが `TravelExecutor` を使う。Weatherは `local_weather_stub`、Travel readは `local_travel_read` として実行する。その他の未実装Toolは `StubExecutor` を使う。実Weather API、Travel DB、Developer実処理、Home Assistant、OpenAI API、MCPなどの外部実行は行わない。

Runtimeは `execute_stub` 内で `ExecutorRegistry.get_executor(tool.id, tool.skill_id)` を呼び、返されたexecutorに実行を委譲する。Runtime本体には `if tool_id == ...` のようなTool別分岐を置かない。

現在のstub返却例:

```json
{
  "message": "stub execution",
  "tool_id": "get_forecast"
}
```

Weather Executor v0.1は `backend/weather_executor.py` に実装している。

現在のWeather Executor v0.1:

* Weather Skill のみ
* 外部天気APIなし
* `local_weather_stub`
* 副作用なし
* read / low risk
* Runtime safety layer 経由で実行

対象Tool:

* `get_current_weather`
* `get_forecast`
* `get_rain_probability`

`params.location` がない場合は `Okayama` を使う。`get_forecast` は `params.days` がある場合、1日から7日の範囲でローカルのダミーforecast配列を返す。

Weather返却例:

```json
{
  "tool_id": "get_forecast",
  "location": "Okayama",
  "forecast": [
    {
      "date": "today",
      "condition": "unknown",
      "rain_probability": null,
      "temperature": null
    }
  ],
  "source": "local_weather_stub"
}
```

将来拡張:

* 実天気API連携
* location正規化
* forecast日数対応
* キャッシュ
* エラー処理
* source明記
* 家族ダッシュボード連携
* 天気MCP Tool化

Travel Runtime v0.1は `backend/travel_executor.py` に実装している。

現在のTravel Runtime v0.1:

* Travel Skill の読み取りTool
* Travel Skill のguarded write Tool
* 読み取りは `local_travel_read`
* `TravelExecutor`: `backend/travel_executor.py`
* `TravelRepository`: `backend/travel_repository.py`
* `SQLiteTravelStorage`: `backend/travel_storage.py`
* local DB: `storage/travel.db`
* 読み取りは副作用なし、read / low risk
* guarded writeは write / medium risk
* guarded writeは `confirmation_required: true`
* guarded writeは `audit_required: true`
* guarded writeは `admin` かつ `confirmed: true` の場合のみ実行
* `family` / `guest` のwriteは拒否
* Runtime safety layer 経由で実行

実装済みTravel Read Tool:

* `travel.get_trips` (`get_trips`)
* `travel.get_trip` (`get_trip`)
* `travel.get_trip_timeline` (`get_trip_timeline`)

実装済みTravel guarded Write Tool:

* `travel.create_trip` (`create_trip`)
* `travel.create_timeline_item` (`create_timeline_item`)

`travel.get_spots` (`get_spots`) はTool定義のみ存在し、Travel Runtime v0.1の実行対象外である。

`travel.get_spots` の現在の状態:

* `TravelExecutor` に分岐なし
* `TravelRepository` にメソッドなし
* `SQLiteTravelStorage` の通常Tool対象外

Travel返却例:

```json
{
  "tool_id": "get_trips",
  "trips": [],
  "source": "local_travel_read"
}
```

将来的には、`ExecutorRegistry` に以下のようなexecutorを `tool_id` または `skill_id` 単位で追加・拡張する。

* `DeveloperExecutor`
* `HomeExecutor`

外部API、DB-backed execution、write toolsへ進む前に、executorごとのRisk、Audit、Permission、Confirmationとの接続を追加する。

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

Permission Engine v0.1は `backend/permission.py` に実装している。

構成:

* `PermissionDecision`: role、実行許可、理由を表す。
* `PermissionEngine`: Tool定義の `skill_id` / `mode` / `risk_level` と request body の `role` から実行可否を判定する。

現在のPermission v0.1:

* UIなし
* 認証なし
* `role` は request body で指定
* 未指定は `guest`
* role は `admin` / `family` / `guest`
* Weather read は `local_weather_stub`
* Travel read は `local_travel_read`
* その他の未実装Toolは `stub`
* 外部API、DB-backed execution、write toolsは未実装

Roleごとの最小ルール:

* `admin`: すべて許可
* `family`: `mode: read` かつ `risk_level: low` のToolだけ許可
* `guest`: `mode: read` かつ `risk_level: low` のToolだけ許可。ただし `skill_id: developer` は拒否

Permissionで拒否された場合の返却例:

```json
{
  "success": false,
  "tool_id": "restart_service",
  "execution_mode": null,
  "result": null,
  "blocked": true,
  "permission_denied": true,
  "role": "guest",
  "permission_allowed": false,
  "confirmation_required": null,
  "confirmed": true,
  "reason": "guest is not allowed to execute developer tools",
  "errors": []
}
```

この場合、`ConfirmationEngine.decide(...)`、`ExecutorRegistry.get_executor(...)`、executor の `execute(...)` は呼ばない。

Permission拒否時はAudit Logに `runtime.permission_denied` として記録する。

```json
{
  "event_type": "runtime.permission_denied",
  "tool_id": "restart_service",
  "status": "blocked",
  "role": "guest",
  "permission_allowed": false,
  "reason": "guest is not allowed to execute developer tools"
}
```

将来拡張:

* 認証
* session/user連携
* family memberごとの権限
* Toolごとの細かいpermission
* 時間帯制限
* 家族データ/写真/家電操作の個別制限
* Confirmation Engineとの詳細接続

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
* `confirmed: true` の場合のみ確認必須Toolのexecutor実行を許可
* Weather read は `local_weather_stub`
* Travel read は `local_travel_read`
* その他の未実装Toolは `stub`
* 外部API、DB-backed execution、write toolsは未実装

確認不要Toolの返却例:

```json
{
  "success": true,
  "tool_id": "get_forecast",
  "execution_mode": "local_weather_stub",
  "result": {
    "tool_id": "get_forecast",
    "location": "Okayama",
    "forecast": [],
    "source": "local_weather_stub"
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

Audit Log v0.1は、Runtime経由の実行記録、permission denied記録、confirmation block記録を `logs/audit.log` にJSONL形式で1行ずつ追記する。

現在のAudit Log v0.1:

* JSONL保存
* `execute_stub`、`permission_denied`、`confirmation_blocked` を記録
* executor実行結果ではなくRuntimeの実行イベントを記録
* Weather read成功時もAudit対象
* Travel read成功時もAudit対象
* Travel read成功時の `event_type` は現在も `runtime.execute_stub`
* Travel read成功時の `execution_mode` は `local_travel_read`
* UIなし
* DBなし
* 認証なし

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
* `role`
* `permission_allowed`
* `reason`
* `error`

失敗時は可能な範囲で `status: "failed"` と `error` を記録する。

権限でブロックした場合は `event_type: "runtime.permission_denied"`、`status: "blocked"`、`role`、`permission_allowed: false`、`reason` を記録する。

確認でブロックした場合は `event_type: "runtime.confirmation_blocked"`、`status: "blocked"`、`confirmation_required`、`confirmed`、`reason` を記録する。

将来拡張予定:

* `validate` / `dry_run` / real execution も記録
* user / session / request_id の記録
* SQLite化
* UIでの閲覧
* 検索/フィルタ
* Confirmation結果との接続
* Permission判定の詳細化

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
