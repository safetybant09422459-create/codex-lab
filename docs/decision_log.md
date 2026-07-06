# Decision Log

## Decision 0001

### テーマ

このプロジェクトの中心は何か？

### 候補

* 旅行アプリ
* 家族ポータル
* AIエージェント

### 決定

AIエージェント

### 理由

旅行、家電、予定、写真はすべてAIが利用するToolである。

主役は機能ではなくAI。

---

## Decision 0002

### テーマ

旅行アプリをどう扱うか？

### 決定

旅行アプリはJarvisの最初のモジュールとする。

### 理由

旅行アプリは完成形ではなく、Jarvisを構成する一機能である。

---

## Decision 0003

### テーマ

AIの成長方針

### 決定

人間承認型から開始する

### 理由

現在のAIはまだ完全自律には早い。

まずは

AI
↓
提案
↓
人間承認

を採用する。

将来的には自律度を高める。

---

## Decision 0004

### テーマ

記憶の持ち方

### 決定

ハイブリッド方式

### 理由

AI人格の記憶と各モジュールのデータを分離する。

例

* jarvis.db
* travel.db
* garden.db

---

## Decision 0005

### テーマ

将来の利用者

### 決定

家族全員

### 理由

ただし権限管理を導入する。

プライバシーを尊重する。

例

* private
* busy
* family
* shared

---

## Decision 0006

### テーマ

Jarvis vNextの意味判断と実行安全性をどこへ置くか？

### 決定

意味判断を単一のLLM Agent Loopへ集約し、PythonはAgent Host、Action Gateway、Domain Capabilityの
決定的処理だけを担う。Activation RAGはRecall Index、EvidenceはGrounded Factへ整理する。

### 詳細

[Jarvis vNext Single Agent Loop Architecture](decisions/2026-07-vnext-single-agent-loop-architecture.md)を参照する。

---

## Decision 0007

### テーマ

SkillとProviderの責務をどう分けるか？

### 決定

Skillはユーザーから見える能力・機能単位、Domain ProviderはCoreが利用する能力提供境界とする。
ProviderはSkillとは別の頭脳や必須microserviceではなく、MCP、REST API、Local Serviceで交換可能な契約面である。

### 詳細

[Domain Provider Responsibility Boundary](decisions/2026-07-domain-provider-boundary.md)を参照する。

---

## Decision 0008

### テーマ

複数ChannelとProviderが共有する1ターンの処理契約をどう定めるか？

### 決定

Jarvis CoreにAgent Loopを一つだけ置き、全Channelを共通Turn Contractへ正規化する。LLMがOperation選択、
結果評価、質問、最終回答を担い、Runtimeが検証、Permission、Confirmation、Audit、実行を担う。
Provider結果はprovenance、visibility、limitationsを持つObservationとして同じLoopへ戻す。

### 詳細

[Turn Contract / Single Agent Loop](decisions/2026-07-turn-contract-single-agent-loop.md)を参照する。

---

## Decision 0009

### テーマ

Jarvis CoreはLLMへ何を渡し、LLMから何を受け取るか？

### 決定

全Channel、Skill、Domain Providerで一つのLLM Contractを共有する。Coreは共通contextとconversation stateを
LLMへ渡し、LLMは`answer`、`ask_clarification`、`call_operation`、`request_confirmation`、`refuse`の
いずれか一つだけを返す。会話継続と話題転換もLLMがAction内で外部化し、Pythonはschema validationと
Runtime接続だけを担う。内部思考やchain-of-thoughtは契約、保存、監査の対象にしない。

### 詳細

[Jarvis Core LLM Contract](decisions/2026-07-llm-contract.md)を参照する。

---

## Decision 0010

### テーマ

Catalogへ何を置き、何を置かないか？

### 決定

Catalogは宣言であり判断ロジックではない。Operation、Capability、Dashboard Catalogを分離し、ユーザー意図、
Provider / Operation選択、回答、現在の表示候補はLLM / Jarvis Coreが判断する。Pythonは読込、validation、
principal / permission / visibility filter、Runtime safety、transport mappingを担う。

### 詳細

[Catalog Principle / Guardrail](decisions/2026-07-catalog-principle.md)を参照する。

---

## Decision 0011

### テーマ

Conversation Qualityを改善するとき、Python Brainの再発をどう防ぐか？

### 決定

会話品質はContext、Observation、Provider契約、Catalog説明、Memory、LLM promptの改善によって上げ、Pythonへ
意図・話題・Provider / Operation選択・Clarification・意味的fallbackを追加しない。Conversation Quality Testを
自然な会話の評価と同時にPython Brain Regression Guardとして扱う。

### 詳細

[Conversation Quality / Python Brain Regression Guard](decisions/2026-07-conversation-quality-python-brain-regression-guard.md)を参照する。

---

## Decision 0012

### テーマ

Observationへ何を置き、どこからを意味判断として禁止するか？

### 決定

Observationは観測された事実と利用条件だけを持つ。Providerは実行結果から決定的factsを生成でき、Runtime / Agent
Hostはvisibility、limitations、provenance、freshnessを付与できるが、解釈、意図、次Action、回答、Provider /
Operation選択、UI表示判断はLLM / Jarvis Coreまたは将来のPresentation Contractへ残す。

### 詳細

[Observation Guardrail](decisions/2026-07-observation-guardrail.md)を参照する。

---

## Decision 0013

### テーマ

Observationを過去の会話でどう参照し、現在の真実とどう分離するか？

### 決定

Observationは取得時点の会話証拠であり、現在値のキャッシュではない。Conversation Stateは会話履歴、Observationは
この会話で取得した事実、Providerは現在の真実、Memoryは長期記憶を担う。Observationだけで十分かProviderを
再実行するかはLLMが判断し、Pythonは保存、visibility、size制限、redactionに限定する。

### 詳細

[Observation Reference Principle](decisions/2026-07-observation-reference-principle.md)を参照する。

---

## Decision 0014

### テーマ

Memoryを何として保持し、Conversation State、Observation、Entity Context、Providerからどう分離するか？

### 決定

Memoryは長期的に有用と思われる知識であり、真実ではない。現在状態はDomain Providerから取得する。
Conversation Stateは今回の会話、Observationは取得時点の会話証拠、Entity Contextは今回参照可能なEntity候補、
Domain Providerは現在のSource of Truthへの能力境界、Memoryは会話を越える長期知識を担う。

Memoryの採用、Provider再取得、ObservationからMemory候補への昇格はLLMが判断する。Pythonは保存、更新、削除、
visibility、retention、redactionに限定し、重要度、推薦、意味的ranking、要約、回答、Provider / Operation選択、
keyword / topic判定を担わない。

### 詳細

[Memory Principle / Responsibility Boundary](decisions/2026-07-memory-principle.md)を参照する。
