# Current Status

## 目的

この文書は、ChatGPTがJarvisの現在地を判断するための実装状態まとめである。

元docsには設計メモと実装済み情報が混在しているため、ここでは「現在動くもの」「Tool定義だけあるもの」「未実装」を分ける。

## リポジトリ

対象:

* `/mnt/nas/projects/codex-lab`

触らない:

* `/mnt/nas/projects/project`

本番旅行アプリ `/mnt/nas/projects/project` は対象外。既存Travel DBが参照される場合もLegacy Dataとして扱い、直接編集しない。

## Jarvis Dev

Jarvis Dev v0.3は、スマホブラウザからこのリポジトリ上のJarvis Core / MCP / アプリ開発を進めるためのAI開発PMツールのプロトタイプである。

起動:

```bash
cd /mnt/nas/projects/codex-lab
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

実運用:

* systemd service: `jarvis-dev`
* port: `8001`
* 旧おでかけアプリのport `8000` と混同しない

検証用Python:

```bash
./.venv/bin/python scripts/check_runtime_api.py
```

## 現在の主要実装

Implemented:

* FastAPI app: `backend/main.py`
* Skill Registry: `skills/*/skill.json`
* Tool Registry: `tools/*/*.json`
* Runtime v0.1
* Audit Log v0.1
* Executor Registry v0.1
* Confirmation Engine v0.1
* Permission Engine v0.1
* Weather Executor v0.1
* Travel Executor / Repository / SQLiteTravelStorage
* Photo Executor / Repository / ImmichAdapter
* Jarvis Shell frontend
* Developer UI
* Runtime Execute UI

## Runtime API

現在利用可能:

* `GET /api/runtime/tool/{tool_id}`
* `POST /api/runtime/validate`
* `POST /api/runtime/dry-run`
* `POST /api/runtime/execute`
* `GET /api/audit`

実行フロー:

```text
API / UI
↓
RuntimeService
↓
Tool Registry
↓
Input Validation
↓
Permission Engine
↓
Confirmation Engine
↓
ExecutorRegistry
↓
Skill Executor
↓
Repository / Adapter / Storage
```

`role`未指定時は`guest`。

`confirmed`未指定時は`false`。

## Web / Developer API

主なAPI:

* `GET /`
* `POST /api/run`
* `GET /api/project`
* `GET /api/skills`
* `GET /api/tools`
* `GET /api/logs`
* `GET /api/changes`
* `GET /api/diff?path=<path>`
* `POST /api/commit`
* `POST /api/push`
* `GET /api/service/status`
* `POST /api/service/restart`

注意:

* この依頼ではgit commit / git pushは禁止。
* Jarvis Dev UIにはCommit / Push機能があるが、人間の明示操作用である。
* Service restartは確認付きの管理操作として扱う。

## Travel API

実装済みAPI:

* `GET /api/travel/trips`
* `GET /api/travel/trips/{trip_id}`
* `GET /api/travel/trips/{trip_id}/photos`
* `GET /api/travel/spots/{spot_id}`

これらはRuntime safety layer経由でTravel Tool / Photo連携を利用する。

## Photo API

実装済みAPI:

* `GET /api/photo/assets/{asset_id}/thumbnail`
* `GET /api/photo/assets/{asset_id}/preview`

Photo Tool:

* `get_photos`
* `get_asset`

PhotoRepositoryはImmichAdapterを利用する。Immich設定やAPIエラーはPhoto層で扱う。

## Tool / Skill一覧

### Weather

Skill:

* `weather`
* `mode: read`
* `risk_level: low`
* `confirmation_required: false`
* `audit_required: false`

Tools:

* `get_current_weather`
* `get_forecast`
* `get_rain_probability`

実行:

* `WeatherExecutor`
* `execution_mode: local_weather_stub`
* 外部天気APIなし
* 副作用なし

### Travel

Skill:

* `travel`
* `mode: mixed`
* `risk_level: medium`
* `confirmation_required: true`
* `audit_required: true`

Read Tools:

* `get_trips`
* `get_trip`
* `get_trip_timeline`
* `get_spots`
* `get_spot`
* `get_trip_photos`
* `get_spot_photos`

Write Tools:

* `create_trip`
* `create_timeline_item`
* `set_trip_cover_image`
* `set_spot_cover_image`

実装:

* `TravelExecutor`
* `TravelRepository`
* `SQLiteTravelStorage`
* DB: `storage/travel.db`

Travel guarded write条件:

* `admin`
* `confirmed: true`
* Tool定義が`confirmation_required: true`
* Audit記録あり

### Photo

Skill:

* `photo`
* `mode: mixed`
* `risk_level: medium`
* `confirmation_required: true`
* `audit_required: true`

Tools:

* `get_photos`
* `get_asset`

実装:

* `PhotoExecutor`
* `PhotoRepository`
* `ImmichAdapter`

### Calendar

Skill:

* `calendar`
* `mode: mixed`
* `risk_level: medium`
* `confirmation_required: true`
* `audit_required: true`

Tool:

* `get_events`

現状:

* Tool定義はある
* 詳細Repository / Executorは未整理またはstub扱い

### Garden

Skill:

* `garden`
* `mode: mixed`
* `risk_level: medium`
* `confirmation_required: false`
* `audit_required: true`

Tools:

* `get_tasks`
* `add_task`

現状:

* Tool定義はある
* 詳細Repository / Executorは未整理またはstub扱い

### Home

Skill:

* `home`
* `mode: mixed`
* `risk_level: high`
* `confirmation_required: true`
* `audit_required: true`

Tool:

* `get_home_status`

現状:

* Tool定義はある
* Homeは高リスクSkill候補
* 家電操作系は未実装

### Developer

Skill:

* `developer`
* `mode: mixed`
* `risk_level: high`
* `confirmation_required: true`
* `audit_required: true`

Tools:

* `run_codex`
* `restart_service`

現状:

* Jarvis Dev UIに開発操作APIがある
* Developer操作は高リスク

## 実装済みレイヤー

### RuntimeService

File:

* `backend/runtime.py`

機能:

* `get_tool`
* `validate`
* `dry_run`
* `execute_stub`
* Tool JSONロード
* 必須入力検証
* Permission / Confirmation / Audit連携
* ExecutorRegistry呼び出し

### ExecutorRegistry

File:

* `backend/executors.py`

機能:

* `tool_id` / `skill_id` からExecutorを選択
* Weather / Travel / Photo Executorを構築
* 未実装ToolはStubExecutorへ

### PermissionEngine

File:

* `backend/permission.py`

現在のrole:

* `admin`
* `family`
* `guest`

### ConfirmationEngine

File:

* `backend/confirmation.py`

高リスクまたは確認必須Toolを`confirmed`フラグで判定する。

### AuditLogger

File:

* `backend/audit.py`

最近のAudit Logは`GET /api/audit`で取得する。

## Not Yet / 注意

未実装または注意:

* Confirmation UI
* 本格的な認証
* 本格的なUser / Family / Profile
* Real Weather API
* Calendar Repository
* Garden Repository
* Home Automation実操作
* MCP Tool化
* Google Places Adapter実装
* Place Skill
* Travelの全CRUD
* Memory独立Entity
* Photo共有・Album更新系

## Tool JSON注意

Tool JSONの`input_schema.properties`では、各propertyに`type`が必要である。

1つのTool定義ミスで`/api/tools`が失敗し、Web UIのTool一覧も壊れる。

新Tool追加時の確認:

```bash
python -m json.tool tools/path/to/tool.json
curl -s http://127.0.0.1:8001/api/tools | head -c 500
```

## Roadmap

Phase:

* Phase 0: GitHub管理
* Phase 1: Jarvis Core設計
* Phase 2: Jarvis Core実装
* Phase 3: Calendar Module
* Phase 4: Travel Module
* Phase 5: Chat Operation
* Phase 6: Home Automation
* Phase 7: Voice
* Phase 8: AI Improvement
* Phase 9: Self Expansion

現在地:

* Jarvis Core / Runtime / Tool Registryのv0.1が進行中
* TravelはDB-backed read/writeの一部まで実装済み
* PhotoはImmich Adapter方向で読み取り系が進行中
* Calendar / Garden / Home / DeveloperはTool候補とUI導線が中心

## Jarvis Principle Check

1. Web UIから利用できるか: Jarvis Dev v0.3としてport 8001で利用できる。
2. API / Toolとして利用できるか: Runtime API、Travel API、Photo API、Developer APIがある。
3. 将来MCP Tool化できるか: SkillRepository中心の構造により候補にできる。
4. Jarvis Coreから呼び出せるか: RuntimeService経由で呼び出す設計である。
5. UI依存のロジックになっていないか: 既存UIは入口。重要ロジックはRuntime / Repositoryへ寄せる方針。
6. 読み取り系か更新系か: mixed。Weatherはread、Travel / Photo / Developer等はmixed。
7. 副作用・権限・プライバシー上の注意はあるか: Developer、Home、Photo、Travel writeは特に確認、権限、監査が必要。
