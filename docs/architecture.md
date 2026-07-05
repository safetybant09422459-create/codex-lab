# Jarvis Core Architecture

> Jarvis vNextの採用済み目標Architectureは
> [Jarvis vNext Single Agent Loop Architecture](decisions/2026-07-vnext-single-agent-loop-architecture.md)を参照する。
> 全Channelが共有する1ターンの具体契約は
> [Turn Contract / Single Agent Loop](decisions/2026-07-turn-contract-single-agent-loop.md)を参照する。
> CoreからLLMへ渡すcontextと、LLMが返す5種類のActionは
> [Jarvis Core LLM Contract](decisions/2026-07-llm-contract.md)を参照する。
> 本書のRouter、Planner、Entity Resolution、Response Composer等は現行実装または移行前の用語であり、
> vNextでは独立した意味判断層にしない。

## 目的

Jarvis Coreは、家庭用AIエージェントJarvisの中核である。

旅行、予定、家電、写真、音楽などの機能は、Jarvis Coreから呼び出されるModule / Toolとして扱う。

---

## 基本構造

vNextの目標構造:

```text
Channel
  -> Jarvis Core boundary
       -> LLM Agent Loop
       -> Runtime
       -> Skill / Domain Provider contract
            -> Repository / External Adapter

Memory -> permitted life context
Activation RAG -> optional, unverified candidates only
```

LLM Agent Loopが意図理解、Skill / Tool選択、arguments生成、事実の十分性評価、Clarification、最終回答を担う。
PythonはSession、Principal、budget、validation、authorization、confirmation、audit、execution、timeout、
retry、redactionなどの決定的処理をRuntime、Skill、Repository境界で担い、自然言語の意味判断を持たない。
Action Gateway、Domain Capability、Recall Indexは既存責務の別名として必須化せず、Grounded Factは検証済み
Tool結果のStateとして扱う。名称変更は責務移行後に必要性を再評価する。

```text
Jarvis
├ AI Agent
├ Memory
├ Users
├ Permissions
├ Runtime
├ Tool Registry
├ Notifications
├ Modules
└ Frontend
```

現在の実装構造：

```text
Jarvis Core
↓
Runtime
↓
Tool Registry
↓
Skill Registry
```

read-onlyの候補想起では、CoreからRuntimeと並列の補助層としてActivation RAGを呼ぶ。Activation RAGは
SQLite / Repositoryの正本を思い出す索引であり、RuntimeやRepositoryを置き換えない。

```text
Jarvis Core
  -> Activation RAG -> unverified Entity candidates
  -> Entity Resolution
  -> Runtime / Domain Repository -> canonical Evidence
```

詳細は[Jarvis Core Activation RAG](activation_rag.md)を参照する。

Runtime は Implemented (v0.1) として、Tool Registry に登録されたTool定義の取得、必須入力の検証、dry-run、stub execution を扱う。

現在は Permission Engine、Confirmation Engine、Audit Log、Executor Registry、Weather Executor、Travel Executor、Travel Runtime v0.1 も実装済みである。Travel Runtime v0.1は `SQLiteTravelStorage` による `storage/travel.db` のlocal DB-backed read/writeを含み、`travel.create_trip` と `travel.create_timeline_item` はguarded writeとして扱う。外部APIを使うReal Tool Execution、追加write tools、MCP Tool化は別フェーズで扱う。

Skillの標準構造は以下とする。

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

詳細は[Skill Standard Architecture](skill_standard_architecture.md)に置く。

## Skill / Domain Providerの関係

`Skill` はTravel、Photo、Calendar、Garden、Homeなど、ユーザーから見える能力・機能単位であり、名称は
当面維持する。`Domain Provider` は、そのSkillがJarvis Coreへ能力を提供する契約境界である。Providerは
新しい頭脳、画面、必須microservice、またはSkillと並ぶ第七のトップレベル責務ではない。

```text
Skill（ユーザーから見える能力領域）
└ Domain Provider contract（Coreから見える能力境界）
   ├ Operation / Tool contract
   └ Provider implementation
      ├ Repository
      ├ Storage / DB
      └ External Adapter / API
```

ProviderはCRUD、検索、正本データ取得、外部API呼び出し、Operation実行、Repository等の隠蔽、
ドメイン不変条件や正規化を担う。内部実装のdispatch、Repository選択、fallbackも決定的であればよい。

Providerは、ユーザー意図の解釈、Provider / Operationの会話上の選択、複数Providerを使う計画、結果の
意味評価、Clarification、Persona、会話状態、最終回答を担わない。これらはLLM Agent Loopが担う。
Runtimeは選択済みOperationを検証し、Permission、Confirmation、Auditを適用する。

ProviderのtransportはMCP、REST API、Local Serviceのいずれでもよい。MCPを現時点の第一候補とするが、
Coreはtransportや内部実装へ依存しない。Web UIとJarvis Chatも、画面専用・Chat専用のドメイン処理を
増やさず、同じProvider OperationをRuntime経由で利用する。

本書やActivation RAG文書にある `Provider` は文脈を明示する。能力提供境界は `Domain Provider`、AIモデルの
提供元は `AI Model Provider`、検索文書供給実装は `Activation RAG Provider` と呼ぶ。

Module / MCP Tool候補：

* Travel Tool / MCP
* Calendar Tool / MCP
* Home Tool / MCP
* Photo Tool / MCP
* Developer Tool / MCP

Jarvis Developer は、Jarvis Core本体ではなく、Developer Tool / MCP候補として扱う。

---

## Home / Jarvis 命名整理

`Home` はJarvis本人やトップ画面の名前ではない。

`Home` は既存docs / Skill定義どおり、Home Control / Home Automation系のSkill候補として扱う。家電、家の状態、消し忘れ、在宅、旅行モードなど、家庭内の物理状態や現実世界への作用を扱う能力領域である。現実世界への影響、家族の在宅情報、生活パターン、センサー情報を扱うため、Home Skillは高リスクSkill候補として扱う。

UI上のトップ画面、またはAIがその時に合った情報を表示する入口は `Jarvis` と呼ぶ。`Jarvis` 画面は単なるダッシュボードではなく、Jarvis CoreがTravel、Photo、Garden、Calendar、Home、Developerなどの情報を統合し、今見せるべきものを判断して表示する入口である。

現時点のJarvis画面は「喋らないJarvis」として考える。将来的な双方向会話、音声、通知、自律提案の土台にはなるが、初期段階では表示、確認、提案、操作入口を中心に扱う。

用語の違い:

| 用語 | 意味 | 扱う範囲 |
| --- | --- | --- |
| Jarvis | 家庭用AIエージェント全体、またはUI上のトップ入口 | ユーザーに見える入口、人格、統合体験 |
| Jarvis Core | Skill、Tool、Runtime、Memory、AI Agentをつなぐ中核 | 判断、調停、権限、Tool実行境界への接続 |
| Jarvis screen | UI上のトップ画面 | 今見るべき情報、提案、確認、入口の表示 |
| Home Skill | Home Control / Home Automation系Skill | 家電、家の状態、消し忘れ、在宅、旅行モード |

Jarvis Shell v0.1を作るとき、ナビゲーションはJarvisをトップ入口とし、各Skillを並列の能力領域として扱う。

```text
Jarvis
├ Travel
├ Photo
├ Garden
├ Calendar
├ Home
└ Developer
```

この構造では、`Home` は他のSkillと同列であり、トップ画面やJarvis Coreの別名にはしない。Jarvis画面の表示判断はCore / Agent / Tool結果に基づくべきで、UIコンポーネント固有の条件分岐に閉じ込めない。

---

## 設計原則

### 1. AIが主役

画面や機能ではなく、AIエージェントが中心。

各機能はAIが使うToolである。

---

### 2. Webアプリ必須

チャットだけではなく、ユーザーが触って確認できるWebアプリを持つ。

理由：

* ワクワク感がある
* 実物を触って判断できる
* 将来AIが作った機能をプレビューできる

---

### 3. Tool First

すべての機能はToolとして設計する。

例：

```text
calendar.create_event
calendar.list_today_events
travel.create_trip
travel.add_spot
appliance.turn_off
photo.show_on_tv
notification.send
```

---

### 4. Moduleは独立可能

各ModuleはJarvis Coreに統合されるが、単体でも動作できるようにする。

例：

```text
modules/travel
modules/calendar
modules/appliance
modules/photo
modules/garden
```

---

### 5. AI Providerは交換可能

Jarvis本体は特定のAIに依存しない。

```text
AI Adapter
├ OpenAI
├ Claude
├ Gemini
└ Local AI
```

---

## 主要コンポーネント

## Jarvis Core

Jarvis Coreは、Jarvis全体の中核として、ユーザー、権限、記憶、Tool、Runtime、AI Agentをつなぐ調停層である。

Coreは特定の画面、特定のSkill実装、特定のAI Provider、特定の外部APIに依存しない。

Coreが担当すること:

* ユーザー要求を、AI Agent、Tool、Memory、Runtimeへ渡すための共通入口を持つ
* どのUser / Role / Contextで処理しているかを保持する
* Skill / Tool Registryを参照し、利用可能な能力を把握する
* Runtimeを通してTool実行、入力検証、権限確認、確認要求、監査へ進める
* Memoryから必要な文脈を取得し、必要に応じて記憶として保存する
* AI Agentに判断を依頼し、最終的な実行はRuntimeやTool境界へ委譲する
* Web UI、API、MCP、音声、チャットなど複数入口から同じ機能を使えるようにする

Coreが担当しないこと:

* UI画面固有の表示状態やDOM操作
* Skill内部のドメインロジック
* Toolの直接実行
* DB、外部API、ファイル、家電などへの直接アクセス
* AI Provider固有のAPI呼び出し詳細
* Memoryの保存形式や検索アルゴリズムの詳細

### Runtimeとの境界

Runtimeは、Toolを安全に実行するための実行境界である。

CoreはRuntimeを呼び出す側であり、Runtimeの中で行う入力検証、Permission、Confirmation、Audit、Executor選択を直接実装しない。

```text
Jarvis Core
↓
Runtime
↓
Permission / Confirmation / Audit
↓
ExecutorRegistry
↓
SkillExecutor
```

Coreの責務:

* 誰が、どの文脈で、どのToolを使いたいかをRuntimeへ渡す
* Runtimeのvalidate / dry-run / execute結果を受け取り、ユーザーやAI Agentへ返す
* 確認が必要な場合、UIや会話入口へ確認要求を戻す

Runtimeの責務:

* Tool定義の取得
* 入力検証
* 権限判定
* 実行前確認の要否判定
* Audit Log記録
* ExecutorRegistry経由の実行委譲

RuntimeはSkill固有ロジックを持たない。CoreもRuntimeを迂回してToolを直接実行しない。

### Skillとの境界

Skillは、Weather、Travel、Photo、Calendarなどの能力領域である。

CoreはSkillを「利用可能な能力」として扱うが、Skill内部のドメイン判断を持たない。

Coreの責務:

* Skill / Tool Registryから能力一覧を参照する
* AI AgentやUser Contextに基づき、候補Toolを選びやすい形で渡す
* Tool実行時はRuntimeへ委譲する

Skillの責務:

* Skill固有のモデル、Repository、Storage / Adapterを持つ
* Tool入力をSkillのドメイン処理へ変換する
* Tool応答として返せる出力を作る

標準構造:

```text
SkillExecutor
↓
SkillRepository
↓
Storage または External Adapter
```

Skill間連携は、相手SkillのTool / API / Repository抽象を経由する。たとえばTravelが写真候補を必要とする場合、Immichを直接呼ばず、Photo Skillを経由する。

### Memoryとの境界

Memoryは、Jarvisの継続性、人格、判断文脈を支える記憶層である。

MemoryはJarvis Coreの必須基盤であり、Coreが利用方針と安全境界を統治する。一方、保存、検索、
要約、更新はMemory Skillへ委譲する。詳細は
[Jarvis Memory Architecture](memory_architecture.md)を参照する。

CoreはMemoryを利用するが、Memoryの保存形式、検索方式、要約方式を直接持たない。

Coreの責務:

* User Context、会話、Tool実行、Decision、Lessonなどから、Memoryに渡すべき情報を判断する
* AI Agentに渡すために必要なMemoryを取得する
* Memoryの読み取り / 書き込みが権限やプライバシーに反しないようにRuntime / Permissionと連携する

Memory Skillの責務:

* Vision、Decision、Lessons Learned、User Preferences、Important Memoriesを保存する
* 会話ログそのものではなく、将来の判断に使える文脈へ整理する
* ユーザー別、家族共有、privateなどの可視性を扱う
* 検索、要約、重要度、忘却、更新履歴を管理する

MemoryはAI Agentの長期文脈であり、SkillのDBではない。TravelのTripやPhotoのAssetのようなドメインデータは各Skillが持ち、Memoryはそこから抽出された意味や体験を扱う。

### Activation RAGとの境界

Activation RAGは、現在発話から正本Entity候補を軽く広く想起し、Entity Resolutionを補助する
Jarvis Coreのread-only検索層である。DBの代替ではなくDBを思い出すための索引であり、Runtimeの
validation、Permission、Confirmation、Audit、実行責務を持たない。

Coreに置く共通責務:

* Provider中立の`RagDocument` / `RagSearchResult`契約
* 認可scopeを受け取る`ActivationSearch`
* Provider登録、検索上限、timeout、部分障害の調停

Provider / Builderに置く責務:

* Domain Repositoryからの認可済みread
* Domain Entityから再生成可能な検索Documentへのprojection
* Domain固有の語彙、alias、metadata、visibility継承

Travelは最初のProvider / PoCである。Photo、Calendar、Memoryは将来Providerとし、Homeは現実世界へ
作用するActionなのでActivation RAG対象外とする。CoreへTravel固有型を追加しない。

### AI Agentとの境界

AI Agentは、ユーザー要求を解釈し、計画し、Toolを選び、結果を説明する判断層である。

CoreはAI Agentを動かす基盤であり、AI Agentそのものの推論やProvider固有処理を持たない。

Coreの責務:

* AI AgentへUser Context、Memory、利用可能Tool、現在の制約を渡す
* AI Agentの提案を受け取り、実行が必要なものはRuntimeへ渡す
* AI Agentが実行できる範囲を権限、確認、監査で制限する

AI Agentの責務:

* ユーザーの意図理解
* 必要なTool候補の選択
* 実行計画の作成
* 実行結果の要約と説明
* 必要に応じたReflectionや改善提案

AI AgentはToolを直接実行しない。実行はRuntimeを通す。CoreはAI Agentの提案を無条件に実行せず、Runtimeの安全境界を通して扱う。

## 将来必要になるコンポーネント

現在未実装、または骨格のみで、将来Jarvis Coreに必要になるコンポーネント:

| Component | 役割 | Coreとの関係 | 主な注意 |
| --- | --- | --- | --- |
| Memory | 継続的な文脈、人格、Preference、Decision、Lessonを保存する | Coreが読み書きする記憶層 | private / family / sharedの可視性が必要 |
| Activation RAG | SQLite / Repositoryの正本Entity候補を想起する | Entity Resolution前のread-only補助 | 検索結果は正本・Evidence・実行許可ではない |
| Skill Router | ユーザー要求やAI Agentの意図から候補Skill / Toolを選ぶ | CoreとAI Agentの間で候補選択を補助する | UIボタン名に依存しない |
| Notification | 出発時間、予定、提案、確認待ちをユーザーへ通知する | Coreがイベントや確認要求を通知へ渡す | 外部送信、家族通知、既読管理に注意 |
| User Context | 誰が、どこで、何のために使っているかを表す | Coreのすべての判断に付与される | 権限、年齢、端末、場所を扱う可能性がある |
| Planner | 複数Tool実行や段階的な作業手順を組み立てる | AI Agentの計画を構造化し、Coreが実行単位へ分解する | 実行前確認と中断可能性が必要 |
| Reflection | 実行結果、失敗、ユーザー反応から学びを抽出する | CoreがMemoryやDecision Logへ渡す候補を作る | 自動記憶化しすぎない |
| Agent | 意図理解、Tool選択、説明、提案を行う | Coreが制約付きで呼び出す判断層 | Tool直接実行を禁止する |
| Conversation | チャットや音声の会話状態を管理する | Coreへの入口のひとつ | 会話ログとMemoryを混同しない |
| Personality | Jarvisらしい判断傾向、言い方、優先順位を形成する | Memory、Vision、Decision、Lessonから構成される | 口調だけに閉じない |
| AI Provider Adapter | OpenAI、Claude、Gemini、Local AIなどを切り替える | Agent実行時にCoreから間接利用する | Provider固有APIをCoreへ漏らさない |
| MCP Adapter | ToolをMCP Toolとして公開 / 呼び出しする | Core / Runtimeの外部入口になる | 権限、確認、監査をRuntimeへ接続する |
| Event Bus | Tool実行、Memory更新、通知、監査などのイベントを流す | Core内外の疎結合化に使う | 更新系イベントの重複実行に注意 |
| Access Control | User、Role、Visibility、Resourceごとの認可を扱う | Core / Runtime / Memory / Skillが参照する | 家族プライバシーの中心になる |
| Confirmation UI / Flow | 危険操作や更新操作の人間確認を扱う | Runtimeの確認要求をユーザー入口へ返す | 確認済み内容と実行内容の一致が必要 |
| Audit Viewer | RuntimeやCoreの重要操作履歴を表示する | Audit Logを人間が確認する入口 | private情報を表示しすぎない |
| Scheduler | 予定時刻、繰り返し、遅延実行を扱う | Coreが未来のTool実行候補を登録する | 自動実行レベルと確認が必要 |

## AI Agent

ユーザーの指示を理解し、必要なToolを選択する。

将来的には以下を行う。

* 提案
* 実行
* 改善
* PR作成
* 自己拡張

---

## Memory

Jarvisの人格と継続性を支える。

記憶は単なる会話ログではない。

扱うもの：

* Vision
* Decision
* Lessons Learned
* User Preferences
* Important Memories
* Past Failures

---

## Users

家族利用を前提とする。

初期ユーザー：

* Owner
* Adult
* Child
* Guest

---

## Permissions

プライバシーと安全性を守る。

例：

```text
private: 本人だけ
busy: 詳細を隠して予定ありだけ表示
family: 家族に表示
shared: 全員に表示
```

コード変更や家電操作など強い権限が必要な操作は、Owner権限を必要とする。

---

## Tool Registry

Jarvisが使えるTool一覧を管理する。

Skillは能力領域の分類であり、Toolは将来実行される具体的な単位である。

```text
Skill
↓
Tool
↓
Runtime
↓
MCP / Executor
```

役割：

* Skill: Weather、Travel、Garden、Developerなどの能力カテゴリを表す
* Tool: get_forecast、add_task、run_codexなどの呼び出し可能な操作単位を表す
* Runtime: Tool定義の取得、入力検証、dry-run、stub executionを扱う実行境界
* MCP Tool / Executor: Toolの実行先または外部連携として提供される将来実装を表す

Toolは以下の情報を持つ。

* name
* description
* input schema
* risk level
* skill_id
* mode
* status

Toolは将来、以下の入口から呼び出される前提で設計する。

* MCP Tool
* OpenAI Tool Calling
* Voice Command
* Web UI
* Jarvis Core

そのためTool定義はUI依存のロジックを持たない。Web UIはTool Registryを表示または操作する入口のひとつであり、Toolの本体や権限判断はCore / Tool層で扱う。

現在はSkill Registry、Tool Registry、Runtime v0.1が実装済みである。

Runtime v0.1は以下を扱う。

* `get_tool`
* `validate`
* `dry_run`
* `execute_stub`
* `ExecutorRegistry`
* `PermissionEngine`
* `ConfirmationEngine`
* `Audit Log`
* `WeatherExecutor`
* `TravelExecutor`
* Travel Runtime v0.1
* `SQLiteTravelStorage` による `storage/travel.db` のlocal DB-backed read/write
* guarded write: `travel.create_trip`, `travel.create_timeline_item`

Real Tool Execution、追加Travel write tools、MCP実装、OpenAI API接続、音声認識、外部API接続は別フェーズで扱う。

---

## Skill Schema

Skillは、将来Jarvis Coreから呼び出すTool / MCP Tool候補として定義する。

UI専用機能として閉じず、音声、チャット、Web UI、カメラ、MCPのどこからでも呼び出せる単位にする。

各Skillは以下を明確に持つ。

* input_schema: Jarvis CoreやTool呼び出し時の入力
* output_schema: 呼び出し結果として返す出力
* mode: read / write / mixed の区別
* risk_level: low / medium / high のリスク分類
* confirmation_required: 実行前に人間確認が必要か
* audit_required: Audit Logに記録すべきか

readは情報取得のみ、writeはデータ変更や現実世界への作用を持つ処理、mixedは読み取りと更新の両方を含む。

risk_levelは、家族、データ、現実世界への影響度で判断する。家電操作、鍵、外部送信、削除など重大な影響があるSkillはhighとして扱う。

---

## Notifications

Jarvisからユーザーに知らせる仕組み。

例：

* 朝の予定一覧
* 出発時間通知
* 家電消し忘れ通知
* AI提案通知
* PR作成通知

---

## Modules

各機能単位。

初期候補：

```text
calendar
travel
appliance
photo
music
garden
```

---

## Frontend

Webアプリ。

最初はスマホ利用を重視する。

将来的には、AIが生成した機能やUIをプレビューできるようにする。

---

## Deployment

GitHubを正本とする。

基本の流れ：

```text
AI / 人間
↓
GitHub
↓
Raspberry Pi
↓
Deploy
```

将来的には、

```text
AI
↓
PR作成
↓
プレビュー
↓
承認
↓
本番反映
```

を目指す。

---

## Safety

現実世界に影響する操作は慎重に扱う。

例：

* 家電操作
* 予定変更
* 通知送信
* コード変更
* デプロイ

自動実行レベル：

```text
Level 0: 提案だけ
Level 1: 確認して実行
Level 2: 安全なものだけ自動実行
Level 3: 完全自動
```

初期はLevel 0〜1を基本とする。

---

## 初期実装方針

最初に作るべきものは大きな機能ではなく、Jarvis Coreの骨格。

優先順：

1. docs整備
2. architecture定義
3. backend骨格
4. User / Permission
5. Tool Registry
6. Calendar Module
7. Web UI
8. Chat Operation
9. Travel Module移植

---

## 重要な考え

Jarvisは機能を直接知るのではなく、Toolを知る。

未来のAIが新機能を追加しやすいように、最初から増築前提で設計する。
