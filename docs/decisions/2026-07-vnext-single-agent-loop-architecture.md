# Decision: Jarvis vNext Single Agent Loop Architecture

## 日付

2026-07-03

## Status

Accepted（目標Architecture。現行実装は段階移行中）

## 背景

JarvisはWebアプリではなく、Web、Voice、Camera、Chat、Notification、MCPなど複数Channelから使う
生活OSを目指す。意味理解、意図理解、推論、Capability選択、回答生成はLLMの責務であり、Pythonは
安全性と決定的処理を担う。

現行実装にはJarvis Core、Chat Core、Router、Planner、Travel Planner、Entity Resolver、
Clarification Policy、Answer Generator、Response Composer、Evidence Bundleなど、過渡期の互換レイヤーが
ある。個々には移行上の役割があるが、独立層として意味判断を分散すると、LLM Agentとは別にPython側へ
第二の頭脳が生まれる。Channel追加やCapability追加のたびに同じ判断が複製される問題もある。

## 決定

Jarvis vNextは、意味判断を一つの **LLM Agent Loop** へ集約する。全体を次の境界へ収束させる。

```text
Web / Voice / Camera / Chat / Notification / MCP
                         |
                      Channel
                         |
                     Agent Host
       Session / Principal / Budget / Recall / Timeout / Trace
                         |
                  LLM Agent Loop
 Intent / Capability / Arguments / Sufficiency / Clarification / Answer
             |                              ^
             v                              |
                  Action Gateway
 Schema / Authorization / Confirmation / Audit / Execution / Retry
             |                              |
             v                              |
 Domain Capability -----------------> Grounded Fact
 Descriptor / Operation / Handler / Domain Store

Life Context -> Agent Host / LLM Agent Loop
Recall Index -> unverified candidates only
```

`Router`、`Planner`、`Entity Resolution`、`Clarification`、`Answer Generation`は、別々の意味判断層では
なく、一つのLLM Agent Loop内の状態またはstepとして扱う。PythonはLLM出力を型・許可値・budget・
policyに対して検証できるが、自然言語キーワード、固定語彙、独自score、fallback文で意味を再判定しない。

### 1. Channel

Channelは入力を共通turnへ変換し、出力、確認要求、進捗を各媒体へ表現する。認証情報をAgent Hostへ渡すが、
意図、Capability、Tool arguments、回答内容を決めない。Web UIも主役ではなくChannelの一つである。

### 2. Agent Host

Agent Hostは薄いPythonホストであり、Session、Principal、token budget、権限適用済みRecall候補取得、
Agent Loop起動、timeout、cancellation、trace、Provider Adapter接続を担う。loop回数やbudget超過は
決定的に停止できるが、ユーザー発話の意味からloop経路を選ばない。

### 3. LLM Agent Loop

LLM Agent LoopをJarvis唯一の頭脳とする。LLMが、意図理解、Capability選択、Operation arguments生成、
Grounded Factの十分性評価、追加OperationまたはClarificationの判断、最終回答を担う。

LoopはCapability Descriptor、許可されたOperation schema、最小限のLife Context、Recall候補、
Grounded Fact、Action Gatewayの構造化結果だけを入力にする。LLM Provider固有処理はAdapterへ閉じ込める。

### 4. Action Gateway

現行Runtimeを **Action Gateway** へ発展・改名する。schema validation、authorization、confirmation、audit、
execution、idempotency、timeout、retry、secret redactionを担う。LLMの提案を信頼せず、Principalとserver-side
policyを正本として実行可否を決める。

retryはOperationの契約とidempotencyが許す場合だけ行う。ConfirmationはLLMの自然文判断ではなく、
Operation metadataとpolicyに基づく。Action GatewayはCapability選択や回答生成をしない。

### 5. Domain Capability

Travel、Photo、Calendar、Home、Developer、MemoryなどはDomain Capabilityとする。各Capabilityが持つのは
次の境界である。

* **Capability Descriptor**: LLMへ提示できる能力、Operation、risk、必要権限の機械可読な説明
* **Operation**: 明確な入出力schemaとread/write、副作用、confirmation、audit、idempotency契約
* **Handler**: 検証済みOperationをドメイン処理へ接続する決定的adapter
* **Domain Store**: Repository、Storage、External Adapterを含む正本アクセス境界

Capabilityはユーザー発話を分類せず、自然文回答を作らない。Repositoryは正本の取得・保存とドメイン不変条件を
担えるが、会話上の意図や回答方針を判断しない。

### 6. Life Context

Jarvisが会話と継続的関係のために使う文脈を次の三つへ整理する。

* **Session Context**: 現在turn、直近履歴、pending confirmationなど短期の作業状態
* **Profile Context**: Principalに紐づく比較的安定した設定、嗜好、関係性
* **Episodic Context**: 過去の出来事を再利用するための記憶

Travel DB、Photo DB、Calendar DBなどのDomain StoreはLife Contextそのものではない。Memory Capabilityが
Domain Entityを無条件に複製することもない。必要な事実は対象CapabilityのOperationから再取得する。

### 7. Recall Index

現行Activation RAGを **Recall Index** へ改名する。役割は関連しそうなEntity、Episode、Capabilityを
LLMへ候補として提示することだけである。候補は未検証hintであり、Source of Truth、Grounded Fact、認可、
Operation argumentsの確定値ではない。

候補を回答や実行に使う前に、LLM Agent Loopは対応するOperationをAction Gateway経由で呼び、canonical ID、
存在、可視性、最新データを再取得する。検索方式とrankingはRecall Index内部に閉じるが、rankingから
意味上の確定を行わない。

### 8. Grounded Fact

回答根拠の共通envelopeを **Grounded Fact** に統一する。最低限、次を持つ。

| field | 意味 |
| --- | --- |
| `source` | 正本となるCapability / Store / external source |
| `operation` | 事実を取得したOperation |
| `canonical_ids` | 再取得・追跡可能な正規ID |
| `data` | schema検証済みの取得データ |
| `retrieved_at` | 取得時刻 |
| `visibility` | Principalへ開示可能な範囲 |
| `freshness` | 有効期限、観測時刻、stale状態など鮮度情報 |
| `limitations` | 欠損、推定、部分取得、外部障害などの制約 |

Grounded FactはAction Gatewayを通ったread結果から生成する。write結果も確認用Factを返せるが、実行済みという
事実と成功後のDomain状態を区別する。LLMはRecall候補、会話の推測、Capability Descriptorをユーザー固有事実の
回答根拠にしない。一般知識を使う場合はGrounded Factとの境界を回答上で混同しない。

## 現行コンポーネントからvNextへの対応

| 現行コンポーネント / 用語 | vNext概念 | 方針 |
| --- | --- | --- |
| Web UI / Chat API | Channel | 入出力と媒体表現だけに限定する |
| 将来Voice / Camera / Notification / MCP | Channel | 同じAgent Host契約へ接続する |
| Jarvis Core | Agent Host + LLM Agent Loopの公開境界 | Python Coreから意味判断を除き、名称は製品全体の中核境界としてのみ残す |
| Chat Core / Orchestrator | Agent Host + LLM Agent Loop | loop管理はHost、意味判断は単一Loopへ統合する |
| Basic Chat Router / Skill Router | LLM Agent LoopのCapability selection state | 独立Routerを廃止する |
| Planner / Travel Planner | LLM Agent Loopのplanning state | 独立PlannerとSkill別の自然言語判断を廃止する |
| Entity Resolver | LLM Agent Loop + Operationによるcanonical再取得 | 検索候補の決定的ID検証だけGateway / Capability側に残す |
| Clarification Policy | LLM Agent Loopのsufficiency / clarification state | policyは安全上の必須確認と会話上の質問を分離する |
| Answer Generator | LLM Agent Loopのfinal answer state | 独立生成層を廃止する |
| Response Composer | Channel serializer / presentation mapping | 意味判断を除き、決定的な媒体変換だけ残す |
| Evidence Bundle / Evidence Assembly | Grounded Factの集合 | envelopeを一本化し、縮小・redactionはHost / Gatewayで決定的に行う |
| Runtime / safety layer | Action Gateway | 発展的に改名する。既存Runtime APIは移行中の互換入口 |
| Tool Registry / Skill Registry | Capability Descriptor / Operation catalog | 二重metadataを段階的に共通契約へ統合する |
| Executor Registry / Skill Executor | Operation Handler dispatch / Handler | 実装選択と入出力adapterとして残す |
| Skill Repository / Storage / External Adapter | Domain Store | 正本とProvider詳細の境界として残す |
| Skill / Module | Domain Capability | 用語をCapabilityへ統一する |
| Memory | Life Context + Memory Capability | 会話文脈とMemoryのドメイン操作を分離する |
| Conversation State / Working Context | Session Context | server-owned stateへ収束させる |
| Activation RAG | Recall Index | 未検証候補提示という役割を名前で明示する |
| Search Index / Entity Candidate | Recall Index document / candidate | Grounded Factとは明確に分離する |
| Travel / Photo / Calendar DB | 各Domain Store | Memoryとは呼ばず、正本として維持する |

## 廃止・統合・改名

### 不要になる独立概念

* Router / Skill Router
* Planner / Travel Planner
* 意味判断を持つEntity Resolver
* 会話上の曖昧性をPythonで決めるClarification Policy
* Answer Generator
* 意味判断を持つResponse Composer
* Skill別Orchestrator

これらの名前がtraceやLoop state名として残ることは許容するが、独立したPythonの頭脳や公開Architecture層には
しない。既存コードは互換期間中ただちに削除しない。

### 統合する概念

* Router、Planner、clarification、answer generationをLLM Agent Loopへ統合する。
* Evidence、Evidence Bundle、Evidence Assemblyの出力をGrounded Fact envelopeへ統合する。
* Skill / Tool metadataをCapability Descriptor / Operation catalogへ統合する。
* Conversation State、Working Context、turn contextをSession Contextへ統合する。
* Runtimeの安全機能と実行制御をAction Gatewayとして一つの信頼境界にする。

### 改名する概念

* Runtime -> Action Gateway
* Skill / Module -> Domain Capability
* Tool -> Operation（外部公開名や既存APIの`tool_id`は互換期間中維持）
* Activation RAG -> Recall Index
* Evidence Bundle -> Grounded Fact set
* Executor -> Handler（Registryによるdispatch実装は維持可能）

## 既存Decisionへの影響

[Chat Core Skill Adapter Architecture](2026-06-chat-core-skill-adapter-architecture.md)が定めた
Entity Resolver、Plan / Execute、Response Composerを独立したChat Core層にする目標は、本Decisionで
置き換える。既存Adapterと公開API互換を安全に移行する実装パターンとしては残すが、vNextの完成形ではない。

[Skill Standard Architecture](2026-06-skill-standard-architecture.md)のRuntime safety boundary、Repository、
Storage / External Adapter分離は維持する。名称をAction Gateway、Handler、Domain Storeへ段階的に合わせる。

## 移行順序

移行は新機能追加ではなく、観測可能な互換移行として行う。一括rewriteはしない。

1. **契約と観測を固定する**
   * 現行Chat / Runtime API、主要benchmark、安全gateのcharacterization testを固定する。
   * traceに現行層、LLM call数、Runtime call、Fact sourceを記録し、意味判断の所在を可視化する。
2. **Grounded Factを先に統一する**
   * 現行EvidenceをadapterでGrounded Factへ変換する。
   * visibility、freshness、limitationsを欠落時に暗黙推定せず、unknownとして表現する。
3. **RuntimeをAction Gateway境界へ揃える**
   * 既存Permission、Confirmation、Audit、Validation、Executor経路を維持する。
   * idempotency、timeout、retry、redactionはOperation metadataに基づく決定的機能として不足分だけ追加する。
   * API / `tool_id`の改名は後回しにし、先に責務を揃える。
4. **Capability契約を正規化する**
   * 既存Skill / Tool JSONからCapability Descriptor / Operation viewを生成し、metadata二重管理を避ける。
   * Travelを最初の移行対象にするが、Travel固有語彙を共通契約へ入れない。
5. **Agent Hostを抽出する**
   * Session、Principal、budget、Recall取得、timeout、traceを既存Orchestratorから分離する。
   * Pythonの自然言語分岐を追加せず、既存ChannelとAPI互換を保つ。
6. **単一LLM Agent Loopへ縦に移行する**
   * まずread-onlyの代表turnで、Capability選択から最終回答までを一つのLoopへ通す。
   * Action Gateway以外からDomain Storeへ到達させない。
   * benchmarkでFact根拠、安全性、clarification、latency、token budgetを比較する。
7. **旧意味判断層を縮退・削除する**
   * Router、Travel Planner、Entity Resolver、Clarification Policy、Answer Generator、Composerの順ではなく、
     代表turnごとに不要になった経路を縦に削除する。
   * 全consumerが新経路へ移るまで互換serializerは残す。削除は別Decision / review可能な変更に分ける。
8. **ChannelとCapabilityを順次接続する**
   * Web / Chatで安定後、Voice、Camera、Notification、MCPを同じHost / Gateway契約へ接続する。
   * Channel固有判断をCoreへ逆流させない。

各段階で、権限、Confirmation、Auditが迂回される、Recall候補がFact扱いされる、既存API互換が説明なく
壊れる、またはbenchmarkで根拠のない回答が増える場合は次段階へ進まない。

## 採用しない案

* Pythonのkeyword、正規表現、固定回答、score閾値でLLMの意味判断を補完する。
* Channelごと、Capabilityごとに独立Agent / Planner / Routerを持つ。
* Recall Indexを正本、認可、回答根拠として使う。
* Domain DBをすべてMemory DBへ統合する。
* vNext名称へ一括renameして既存APIと実装を同時に壊す。

## 影響と再検討条件

良い影響は、意味判断の所在が一つになり、Channel / Capability追加でPython側の頭脳が増えないこと、
安全境界と回答根拠が監査可能になることである。一方、単一Loopはtoken、latency、Provider障害の影響を
受けるため、Agent Hostのbudget、timeout、traceと、Action Gatewayの決定的な拒否が必須になる。

再検討は、単一Loopでは満たせない測定済みの安全性・latency要件が現れた場合に行う。その場合も、Pythonへ
自然言語意味判断を戻すのではなく、LLM sub-loop、model routing、context縮小などをProvider中立なAgent Loop
内部の実装として検討する。

## Jarvis Principle Check

1. Web UIから利用できるか: WebをChannelとして同じAgent Hostへ接続できる。
2. API / Toolとして利用できるか: OperationとAction GatewayがUI非依存のAPI / Tool境界になる。
3. 将来MCP Tool化できるか: MCPをChannelまたはOperation公開adapterとして接続できる。
4. Jarvis Coreから呼び出せるか: Agent Host / LLM Agent Loop / Action GatewayがvNextのCore境界になる。
5. UI依存のロジックになっていないか: Channelは入出力だけで、意味判断は単一Loopに置く。
6. 読み取り系か更新系か: Architectureは両方を扱い、Grounded Fact / Recallはread、writeはGatewayでguardする。
7. 副作用・権限・プライバシー上の注意はあるか: Principal、最小開示、Confirmation、Audit、redactionをGatewayとHostで強制する。
