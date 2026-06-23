# Jarvis Architecture

## 目的

この文書は、Jarvis Core、Runtime、Skill、Tool、Web UIの責務境界をまとめる。

Jarvisは、家庭用AIエージェントを中心に、複数SkillをToolとして呼び出す構造を取る。UIは入口であり、ドメイン判断、権限、確認、監査、DB操作の本体ではない。

## 全体構造

```text
Jarvis
├ AI Agent
├ Memory
├ Users
├ Permissions
├ Runtime
├ Tool Registry
├ Notifications
├ Skills / Modules
└ Frontend
```

現在の実装上の主要構造:

```text
Jarvis Core / API / Web UI
↓
Runtime
↓
Permission / Confirmation / Audit
↓
ExecutorRegistry
↓
SkillExecutor
↓
SkillRepository
↓
Storage または External Adapter
↓
DB / 外部API
```

## Jarvis Core

Jarvis Coreは、Jarvis全体の中核として、AI Agent、User、Permission、Memory、Tool、Runtime、Skillを調停する。

Coreが担当すること:

* User / Role / Contextを把握する
* 利用可能なSkill / ToolをTool Registryから把握する
* AI Agentに判断を依頼する
* Tool実行はRuntimeへ渡す
* Memoryから文脈を取得し、必要に応じて記憶する
* Web UI、API、MCP、Chat、Voiceから同じ能力を使えるようにする

Coreが担当しないこと:

* UI画面固有のDOM操作や表示状態
* Skill内部のドメインロジック
* Toolの直接実行
* DB、外部API、家電、ファイルへの直接アクセス
* AI Provider固有のAPI詳細

## Runtime

Runtimeは、Toolを安全に実行するための実行境界である。

Runtimeの責務:

* Tool JSONのロード
* 必須入力の検証
* Permission Engineによる権限判定
* Confirmation Engineによる確認要否判定
* Audit Log記録
* ExecutorRegistry経由の実行委譲

RuntimeはSkill固有ロジックを持たない。`if tool_id == ...` のようなTool別分岐をRuntime本体へ増やさず、ExecutorRegistryに委譲する。

現在のRuntime API:

* `GET /api/runtime/tool/{tool_id}`
* `POST /api/runtime/validate`
* `POST /api/runtime/dry-run`
* `POST /api/runtime/execute`
* `GET /api/audit`

`POST /api/runtime/execute` は、確認、権限、監査を通したうえでExecutorを呼ぶ。関数名としては `execute_stub` が残っているが、WeatherやTravelなど一部は実Executorに到達する。

## Permission

Permission Engine v0.1は、request bodyの`role`とTool定義の`skill_id`、`mode`、`risk_level`を見て実行可否を判定する。

現在のrole:

* `admin`: 全Toolを許可
* `family`: readかつlow riskを許可
* `guest`: readかつlow riskを許可。ただしdeveloper skillは不可

`role`未指定時は`guest`として扱う。

権限がない場合、RuntimeはExecutorを呼ばない。

## Confirmation

Confirmation Engine v0.1は、Tool定義の`risk_level`と`confirmation_required`、request bodyの`confirmed`を見る。

以下は確認が必要:

* `risk_level: high`
* `confirmation_required: true`

`confirmed: true` がない場合、RuntimeはExecutorを呼ばず、Auditにブロックを記録する。

Confirmation UIは未実装。現時点ではAPIの`confirmed`フラグで表現する。

## Audit

Audit Log v0.1は、Runtime実行、権限拒否、確認ブロック、失敗を記録する。

Travel readもAudit対象のTool定義が多い。写真、位置、旅行計画、家族情報、開発操作は監査対象にする。

## Skill標準構造

全Skillは以下の標準構造を基本にする。

```text
Runtime
↓
Permission / Confirmation / Audit
↓
ExecutorRegistry
↓
SkillExecutor
↓
SkillRepository
↓
Storage または External Adapter
↓
DB / 外部API
```

各レイヤーの責務:

| layer | 責務 |
| --- | --- |
| Runtime | Toolロード、入力検証、権限、確認、監査、Executor呼び出し |
| ExecutorRegistry | `tool_id` / `skill_id` からExecutorを選ぶ |
| SkillExecutor | Tool入出力adapter、Repository呼び出し、Tool応答整形 |
| SkillRepository | Skillの中心。ドメインロジック、正規化、Storage/Adapter隠蔽 |
| Storage | DB詳細、SQL、永続化、Record変換 |
| External Adapter | 外部API詳細、認証、レート制御、レスポンス正規化 |

重要ルール:

* RuntimeにSkill固有ロジックを書かない
* UIにドメインロジックを書かない
* ExecutorにDBや外部API詳細を書きすぎない
* RepositoryをSkillの中心にする
* StorageはDB詳細を隠蔽する
* External Adapterは外部API詳細を隠蔽する
* Skill間連携は相手SkillのTool / API / Repository抽象を経由する

## Skill間連携

Skill間連携では、相手Skillの内部実装へ直接依存しない。

例: Travelが写真候補を必要とする場合。

```text
TravelRepository
↓
Photo Tool / Photo API / PhotoRepository abstraction
↓
PhotoRepository
↓
ImmichAdapter
```

TravelはImmichを直接呼ばない。PhotoがImmich以外へ移ってもTravelの設計を変えずに済むようにする。

## Jarvis Shell

Jarvis Shellは、Jarvis Web UI全体の共通入口である。

初期ナビゲーション:

```text
Jarvis
├ Travel
├ Photo
├ Garden
├ Calendar
├ Home
└ Developer
```

`Jarvis` はトップ入口であり、`Home` とは呼ばない。`Home` はHome Control / Home Automation Skillである。

Shellが担当すること:

* 共通レイアウト
* 画面切替
* ナビゲーション
* 各Skill画面の受け皿
* Developer UIへの導線
* CoreやRuntimeからの表示結果、確認要求の表示

Shellが担当しないこと:

* Skill固有のドメインロジック
* Runtime実行ロジック
* DB操作
* AI判断
* Tool直接実行

## Jarvis Screen

Jarvis Screenは、Jarvis Shellのトップ画面である。

現時点では「喋らないJarvis」として扱う。固定ダッシュボードではなく、将来Jarvis CoreやSkill Routerが文脈に応じて表示内容を選ぶ場所である。

表示候補:

* 今日の予定
* 天気
* 次の旅行
* 最近の写真
* Gardenの水やり
* Homeの注意
* Developerの状態
* Jarvisからの提案

全部を常に表示するのではなく、その時に必要なものをCore / Skill / Memory / Tool結果に基づいて選ぶ。

Jarvis Screenは表示先であり、Tool実行主体ではない。更新系操作へ進む場合はRuntimeのPermission / Confirmation / Auditを通す。

## Home命名

`Home` はJarvis本人やトップ画面の名前ではない。

Home Skillは、家電、家の状態、消し忘れ、在宅、旅行モードなどを扱うHome Control / Home Automation系Skillである。

Home Skillは現実世界への作用、在宅情報、生活パターンを扱うため、高リスクSkill候補として扱う。

## Developer Skill

DeveloperはJarvis Core本体ではなく、Developer Tool / MCP候補である。

扱うもの:

* Codex実行
* git状態表示
* diff表示
* service status
* service restart
* 将来のPR作成や改善提案

開発操作は高リスクであり、確認、権限、監査を必須にする。

## Safari First

iPhone / Safariは主要利用端末に含まれる。

Frontend設計では以下を守る。

* Chromeで動いてもSafariで壊れる状態は未完成
* `flatMap` など互換性に不安があるAPIを不用意に使わない
* import先のトップレベル例外でアプリ全体を止めない
* Shell、Runtime Execute、Developer UIの初期化を分離する

## Jarvis Principle Check

1. Web UIから利用できるか: Shell / Screen / Skill画面から利用できる。
2. API / Toolとして利用できるか: Runtime APIとTool定義により利用できる。
3. 将来MCP Tool化できるか: SkillRepositoryを中心にすればMCP Handlerからも呼べる。
4. Jarvis Coreから呼び出せるか: CoreはRuntimeを通してSkillへ到達する。
5. UI依存のロジックになっていないか: 判断と実行をCore / Runtime / Repositoryへ置く前提で、UI依存を避ける。
6. 読み取り系か更新系か: 構造は両方に適用する。更新系は確認と監査を通す。
7. 副作用・権限・プライバシー上の注意はあるか: 写真、予定、旅行、家、開発操作は副作用と権限に注意する。
