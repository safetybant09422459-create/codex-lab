# Decision: Jarvis vNext Responsibility Architecture

## 日付

2026-07-03

## Status

Accepted（目標Architecture。現行実装は段階移行中）

> SkillのCore向け契約面をDomain Providerと呼ぶ語彙整理は、後続の
> [Domain Provider Responsibility Boundary](2026-07-domain-provider-boundary.md)で採用した。Providerは本Decisionの
> Skill責務を分割する第七の判断主体ではない。

## 背景

JarvisはWebアプリではなく、Web、Voice、Camera、Chat、Notification、MCPなど複数Channelから使う
生活OSを目指す。意味理解、推論、計画、Capability選択、評価、回答はLLMだけが担う。Pythonは安全、
実行、正本アクセスなど、入力と結果を決定的に検証できる処理だけを担う。

現行docsと実装には、Jarvis Core、Chat Core、Router、Planner、Travel Planner、Entity Resolver、
Clarification Policy、Answer Generator、Response Composer、Evidence Bundle、Activation RAG、Memoryなどが
ある。また、これらを整理するためにAction Gateway、Domain Capability、Grounded Fact、Recall Index等の
名前も提案されていた。しかし、名前を増やすだけでは責務は減らず、移行前後の用語を二重管理することになる。

本Decisionは名前ではなく責務を決める。既存名の一括変更は行わない。

## 決定

目標Architectureで責務を所有する独立境界は、次の六つだけとする。

| 責務所有者 | 必要な責務 | 持たない責務 |
| --- | --- | --- |
| Channel | 媒体固有の入力取得、共通turnへの変換、出力・確認・進捗の媒体表現 | 意味理解、Skill選択、引数決定、回答方針 |
| LLM Agent Loop | 理解、推論、計画、Skill / Tool選択、引数提案、事実の十分性評価、質問、回答 | 認可の確定、直接実行、DBアクセス、監査 |
| Runtime | session、principal、schema validation、permission、confirmation、audit、実行、timeout、retry、idempotency、redaction、loop上限 | 自然言語の分類、計画、候補の意味評価、回答生成 |
| Skill | 利用可能な能力とTool契約、決定的なドメイン処理 | 発話分類、会話上の計画、自然文回答、Runtime安全機能 |
| Repository | 正本の取得・保存、ドメイン不変条件、Storage / 外部APIの隠蔽 | 会話意図、回答方針、検索候補だけによる事実確定 |
| Memory | 継続的に保持する生活文脈、その検索・更新・忘却 | turn中の作業状態、各Skillの正本データの複製、実行許可 |

`Jarvis Core`はこれらを接続する製品上の公開境界を指す名前として残せるが、七つ目の判断主体ではない。
`Chat Core`もChat Channelから同じ境界を利用する現行の互換実装であり、独立した頭脳にはしない。

```text
Channel
   |
   v
Jarvis Core boundary
   +-- LLM Agent Loop: understand -> choose -> inspect -> answer / ask
   +-- Runtime: validate -> authorize -> confirm -> execute -> audit
                           |
                           v
                    Skill -> Repository
   +-- Memory: permitted life context
```

LLMの提案は実行許可ではない。すべてのTool実行とMemory更新はRuntimeを通る。RuntimeはLLM出力をschema、
許可値、principal、policy、budgetに対して検証できるが、自然言語キーワード、固定語彙、独自score、
fallback回答で意味を再判定しない。

## 責務レビュー

| 現行概念 | 必要性 | 統合先 / 扱い | LLMかPythonか |
| --- | --- | --- | --- |
| Jarvis Core | 公開・統合境界として必要 | 責務所有者を増やさず、六境界の接続名とする | 判断はLLM、安全な接続はPython |
| Chat Core / Orchestrator | 専用Architectureとして不要 | ChannelとRuntimeへ分解し、意味判断はLLM Agent Loopへ統合 | loop制御だけPython |
| Router / Skill Router | 独立概念として不要 | Skill選択というAgent Loop state | LLM |
| Planner / Travel Planner | 独立概念として不要 | 次に何をするかというAgent Loop state | LLM |
| Evaluator / Reflection | 独立概念として不要 | 結果・事実の十分性を判定するAgent Loop state | LLM |
| Entity Resolver | 意味判断層として不要 | 候補選択はLLM、ID・存在・可視性の検証と再取得はRuntime経由のSkill / Repository | LLM + 決定的Python |
| Clarification Policy | 会話判断層として不要 | 情報不足なら質問するAgent Loop state。安全上のConfirmationだけRuntimeに残す | 質問はLLM、確認強制はPython |
| Answer Generator / Responder | 独立概念として不要 | Agent Loopの最終回答state | LLM |
| Response Composer | 意味判断層として不要 | LLM回答をChannel形式へ変える決定的serializerだけ残す | Python / Channel |
| Evidence Bundle / Assembly | コンポーネントとして不要 | Runtimeで検証・権限適用されたTool結果のturn state | Pythonが検証、LLMが評価 |
| Runtime / safety layer | 必要 | 既存Runtimeへ安全機能と実行制御を集約 | Python |
| Action Gateway | 新概念として不要 | Runtimeの責務説明または将来の別名にすぎないため、現時点ではRuntimeへ吸収 | Python |
| Skill / Module | 必要 | 能力とTool契約の所有者。既存Skillを維持 | 決定的Python |
| Domain Capability | 新概念として不要 | Skillと同じ責務なのでSkillへ吸収 | 決定的Python |
| Tool / Operation | 必要 | Skillが公開しRuntimeが実行する契約。名称変更しない | schemaと実行はPython |
| Registry / Executor | 実装として必要になり得る | RuntimeとSkill内部のdispatchであり、トップレベル概念にしない | Python |
| Repository / Storage / External Adapter | 正本境界として必要 | Repositoryを公開境界とし、Storage / Adapterは内部実装 | Python |
| Memory | 必要 | 生活文脈だけを所有。read / writeはSkillとRuntimeの通常境界を使う | 選択・要約はLLM、保存・権限はPython |
| Conversation / Working Context | 独立基盤として不要 | session内の一時state | Pythonが保持、LLMが利用 |
| Activation RAG | 候補検索が有効な場合だけ必要 | Repository / Memoryから再生成できる任意の派生索引。回答根拠にはしない | 検索はPython、候補評価はLLM |
| Recall Index | 新概念として不要 | Activation RAGの責務説明または別名にすぎない。トップレベル境界にしない | 同上 |
| Grounded Fact | 状態として必要 | 検証済みTool結果を示すturn内のデータ状態。サービスや層にしない | Pythonが保証情報を付与、LLMが回答に利用 |

## Stateとして扱うもの

Agent Loopは固定された複数コンポーネントのパイプラインではなく、必要に応じて次の状態を遷移する。

| State | 内容 | 永続的な独立コンポーネントにしない理由 |
| --- | --- | --- |
| understanding | 現在の要求と文脈の理解 | Routerを別の頭脳にしないため |
| selecting | Skill / Toolの選択と引数提案 | Skill別Plannerを増やさないため |
| inspecting | Tool結果、候補、制約の評価 | EvaluatorやEntity Resolverを別層にしないため |
| asking | 情報不足時のclarification | 会話上の質問をRuntime policyと混ぜないため |
| answering | 根拠と制約を踏まえた回答 | Answer Generatorを分離しないため |
| awaiting_confirmation | Runtimeが実行を停止している状態 | LLM判断ではなくserver-owned session stateだから |
| completed / failed / cancelled | turnの終端 | timeout、budget、cancelを決定的に扱うため |

planning、evaluation、responseは処理の説明やtrace labelとして使えるが、公開Architecture層、独立service、
独立Python判断器にはしない。内部state名も実装前に固定する必要はない。

## 事実、候補、Memoryの区別

概念を減らしても、信頼状態は混ぜない。

| 状態 | 意味 | 回答・実行での扱い |
| --- | --- | --- |
| candidate | Activation RAG等が返す未検証候補 | そのまま根拠や確定引数にしない |
| verified tool result | Runtimeを通り、Repositoryまたは明示された外部sourceから得た検証済み結果 | 現在turnの事実として利用できる |
| general knowledge | LLMの一般知識 | 家族固有・現在状態の事実と混同しない |
| memory | 権限適用済みの生活文脈 | 現在のドメイン状態が必要ならRepositoryから再取得する |

`Grounded Fact`という語をenvelopeや型の説明に使うことは妨げない。ただし、それ自体を独立した保存層、
サービス、Repositoryの代替にはしない。最低限、source、取得Tool、canonical ID、取得時刻、visibility、
freshness、limitationsをTool結果に付与できるようにする。欠落値をPythonが意味推論で補完してはならない。

Activation RAGも同様に、検索需要と評価結果がある場合だけ維持する。索引は正本から再生成可能とし、検索前に
権限scopeを適用する。候補を利用する前にRuntime経由で正本を再取得する。Capability候補検索を同じ索引へ
入れるかは、静的なSkill / Tool一覧で不足する測定結果が出るまで決定しない。

## 概念統合案

1. Router、Planner、Evaluator、Entity Resolverの意味判断、Clarification、Answer Generatorを一つの
   LLM Agent Loopへ統合する。
2. Chat Core / Skill別Orchestratorのloop制御、session、budget、timeout、traceをRuntimeへ統合する。
3. Permission、Confirmation、Audit、Validation、Executor dispatchを既存Runtimeの一つの信頼境界に保つ。
4. Domain Capabilityを既存Skillへ、Operationを既存Toolへ吸収し、metadataの二重管理を作らない。
5. Evidence Bundleは検証済みTool結果の集合というturn stateにし、独立Assembly層をなくす。
6. Conversation State、Working Context、pending actionをserver-owned session stateへ統合する。
7. Activation RAG / Recall Indexは正本ではなく、Repository / Memoryに従属する任意の派生索引として扱う。
8. Memoryは生活文脈に限定し、Travel、Photo、Calendar等の正本は各Repositoryに残す。

## 削除候補

完成形の独立Architecture概念から、次を削除する。

* Chat Coreという別の頭脳
* Router / Skill Router
* Planner / Travel Planner
* Evaluator / Reflection service
* 意味判断を持つEntity Resolver
* 会話上のClarification Policy
* Answer Generator / Responder
* 意味判断を持つResponse Composer
* Evidence Assembly service
* Skill別Orchestrator
* Action Gateway、Domain Capability、Recall Indexという既存責務の別名
* Grounded Factという独立serviceまたは保存層

現行コード上の同名クラスやmoduleは、互換経路が利用している間は直ちに削除しない。削除対象なのはまず
完成形の責務と設計上の必須性であり、物理削除はcharacterization testとconsumer移行後に行う。

## 最終的に残る最小概念

最小構成は `Channel / LLM Agent Loop / Runtime / Skill / Repository / Memory` である。

* Jarvis Core: 六つを接続して外部へ公開する製品境界
* Tool result、候補、session、plan、evaluation、answer: 境界間を流れるState
* Registry、Executor、Storage、Adapter、索引: 必要に応じて境界内部へ置く実装詳細

MemoryをSkillとして実装することはできるが、生活文脈という責務は他のドメイン正本と区別する。したがって、
実装上の経路を共通化してもArchitecture上の責務まで消さない。逆に、Recall用索引は性能・発見性の最適化であり、
正しさの境界ではないため最小構成の必須概念に含めない。

## 既存Decisionへの影響

[Chat Core Skill Adapter Architecture](2026-06-chat-core-skill-adapter-architecture.md)が定めたEntity Resolver、
Plan / Execute、Response Composerを独立したChat Core層にする目標は本Decisionで置き換える。既存Adapterと
公開API互換を維持する移行実装としてのみ残す。

[Skill Standard Architecture](2026-06-skill-standard-architecture.md)のRuntime、Executor、Repository、Storage /
External Adapter分離は維持する。ただし、Executor、Storage、Adapterはトップレベル概念ではなく、それぞれ
Runtime、Skill、Repository内部の実装詳細として扱う。

[Jarvis Memory Architecture](../memory_architecture.md)のMemoryとDomain Repositoryを分離する判断は維持する。
同文書中のPlanner、Answer Generator、Resolver等は移行前の呼称として読み、本DecisionのAgent Loop stateへ
読み替える。

## 移行方針

責務を先に移し、renameと一括rewriteは行わない。

1. **現行挙動を固定する**
   * Chat / Runtime API、安全gate、主要benchmarkのcharacterization testを固定する。
   * traceでLLM判断、Runtime拒否、Tool実行、正本sourceを区別する。生の思考過程や秘密は記録しない。
2. **信頼状態を明示する**
   * 現行Evidenceへsource、visibility、freshness、limitationsを可能な範囲で追加する。
   * 未知の値は`unknown`とし、意味推論で埋めない。候補と検証済み結果を型またはstatusで分離する。
3. **Runtime境界を完成させる**
   * 既存Permission、Confirmation、Audit、Validation、Executor経路を維持する。
   * session、principal、budget、timeout、cancellation、retry、idempotency、redactionの不足だけを追加する。
4. **Skill / Tool metadataを単一化する**
   * 既存Skill / Tool JSONを正本にし、LLM提示用viewを生成する。別のCapability metadataを作らない。
5. **代表turnを単一Agent Loopへ縦に移す**
   * read-onlyの代表turnから、選択、実行結果評価、回答までを一つのLoopへ移す。
   * Runtime以外からRepositoryへ到達させず、既存Channel / API responseはserializerで維持する。
6. **旧責務を利用経路ごとに削る**
   * Router等を層ごと一括削除せず、新Loopへ移ったturnから旧分岐を外す。
   * Pythonの自然言語分岐、固定回答、Skill別Plannerが残っていないことをdiffとbenchmarkで確認する。
7. **名前変更は最後に判断する**
   * 全consumer移行後、現行名が実際に誤解を生む場合だけ別Decisionでrenameする。
   * Runtime、Skill、Tool、Activation RAGの一括renameを移行条件にしない。
8. **Channelを追加する**
   * Web / Chatで境界を検証後、Voice、Camera、Notification、MCPを同じCore / Runtime契約へ接続する。

権限、Confirmation、Auditが迂回される、候補が事実扱いされる、API互換が説明なく壊れる、または根拠のない
回答が増える場合は次段階へ進まない。

## 採用しない案

* Pythonのkeyword、正規表現、固定回答、score閾値でLLMの意味判断を補完する。
* ChannelまたはSkillごとに独立Agent、Planner、Routerを持つ。
* 検索候補を正本、認可、回答根拠、確定Tool引数として使う。
* Domain DBをMemoryへ統合する。
* 責務が同じ概念へ新しい名前を付け、旧名と並存させる。
* vNext名称への一括renameと実装rewriteを同時に行う。

## 再検討条件

単一Agent Loopでは満たせない安全性、latency、cost要件が測定された場合に再検討する。その場合も、Pythonへ
自然言語判断を戻すのではなく、LLM sub-loop、model routing、context縮小をAgent Loop内部の実装として検討する。

Recall用索引は、正本一覧や通常のRepository検索では発見率が不足することをbenchmarkで確認した場合に必須化を
再検討する。新しい名前は、責務移行後も既存名が誤実行や境界違反を招く証拠がある場合だけ検討する。

## Jarvis Principle Check

1. Web UIから利用できるか: WebをChannelとして同じJarvis Core境界へ接続できる。
2. API / Toolとして利用できるか: Skill / ToolとRuntimeがUI非依存の実行境界になる。
3. 将来MCP Tool化できるか: MCPをChannelまたはTool公開adapterとして同じ境界へ接続できる。
4. Jarvis Coreから呼び出せるか: 六責務を接続する公開境界がJarvis Coreである。
5. UI依存のロジックになっていないか: Channelは媒体変換だけを持ち、意味判断はLLMへ置く。
6. 読み取り系か更新系か: 本Decisionは両方を扱う。候補検索と事実取得はread、保存とActionはguarded writeである。
7. 副作用・権限・プライバシー上の注意はあるか: 全実行をRuntimeへ集約し、最小開示、Confirmation、Audit、redactionを強制する。
