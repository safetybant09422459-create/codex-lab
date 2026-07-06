# Principles

## Principle 1

AI First

JarvisはAIエージェントが主役。

旅行、家電、写真は主役ではない。

---

## Principle 2

Tool First

すべての機能はToolとして設計する。

UIから利用できるだけでなく、

* Chat
* Voice
* Future Robot

からも利用可能にする。

---

## Principle 3

UI / API / MCP First

新機能は可能な限り、UI専用機能として作らない。

以下の3層で考える。

* Web UI
* API / Tool
* MCP Tool候補

新機能を作る時は、将来Jarvis Coreから呼び出せるToolになるか確認する。

確認項目：

* 入力は明確か
* 出力は明確か
* 読み取り操作か、更新操作か
* 副作用があるか
* 権限確認が必要か
* 家族利用・プライバシー面の問題はないか
* 音声やチャットから自然に呼び出せる名前か

重要なロジックはUIに閉じ込めない。

画面ボタンだけでなく、APIやToolからも呼び出せる構造を意識する。

---

## Principle 4

Web UI Required

チャットだけではなく、

触れるWebアプリを持つ。

理由：

* ワクワク感
* プレビュー
* 確認しやすさ

---

## Principle 5

Human Friendly

家族が使いやすいことを優先する。

技術的な美しさだけを追求しない。

---

## Principle 6

AI Model Provider Independent

OpenAI専用にしない。

将来的な乗り換えを考慮する。

---

## Principle 7

Privacy First

家族のプライバシーを尊重する。

例：

* private
* busy
* family
* shared

---

## Principle 8

Module Independence

各Moduleは独立可能であること。

Travelだけでも動く。

Calendarだけでも動く。

---

## Principle 9

Explainability

Jarvisは理由を説明できること。

例：

* なぜ提案したのか
* なぜ実行したのか
* なぜ変更したのか

---

## Principle 10

Trust Before Automation

自動化より信頼を優先する。

最初は

提案
↓
確認
↓
実行

を基本とする。

---

## Principle 11

Future AI Friendly

未来のAIが理解しやすい構造にする。

人間だけではなく、

未来のJarvis自身も読者である。

---

## Principle 12

Growth Through Experience

人格は口調ではない。

人格は

* Vision
* Decision
* Lessons
* Memory

から形成される。

---

## Principle 13

Ideas Are Assets

思いつきを捨てない。

今やらないことと、

忘れることは違う。

すべてIdea Backlogへ記録する。

---

## Principle 14

Build The House First

機能を増やす前に土台を作る。

Jarvisはアプリではない。

AIが住む家である。

---

## Principle 15

Enjoy The Journey

このプロジェクトは趣味であり夢でもある。

効率だけでなく、

ワクワクすることを大切にする。

---

## Principle 16

Safari First / Safari-safe Frontend

Jarvisの主要利用端末には、iPhone / Safari を含める。

Chromeで動いてもSafariで動かない場合は、未完成として扱う。

frontend実装では、Safari互換を優先する。

新しめのJavaScript構文やAPIを不用意に使わない。

特に以下に注意する。

* `flatMap`
* `Map`依存
* optional chaining
* nullish coalescing
* top-levelで落ちるimport依存

frontend JSは、Safariで一部が失敗しても既存Developer UIやRuntime UI全体を巻き込まない構造にする。

Shell / Runtime Execute / Developer UI の初期化はできるだけ分離し、片方の失敗で全体が止まらないようにする。

新規frontend JS追加時は、Safariでの実機確認を必須チェックに含める。

---

## Principle 17

Skill Standard Architecture

Skillは標準レイヤー構造に揃える。

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

RepositoryをSkillの中心にする。

RuntimeはTool JSONロード、入力検証、権限、確認、監査、Executor呼び出しを担当し、Skill固有ロジックを持たない。

ExecutorはTool入出力adapterとして、Toolごとの分岐とRepository呼び出しを担当する。

StorageはDB詳細を隠蔽し、External Adapterは外部API詳細を隠蔽する。

重要ルール:

* RuntimeにSkill固有ロジックを書かない
* UIにドメインロジックを書かない
* ExecutorにDBや外部APIの詳細を書きすぎない
* Skill間連携は相手SkillのProvider Operation / Tool / API契約を経由する
* TravelからImmichを直接呼ばない
* Photo Skillは `PhotoExecutor -> PhotoRepository -> ImmichAdapter` で作る

---

## Principle 18

Domain Provider Boundary

Skillはユーザーから見える能力・機能単位、Domain ProviderはJarvis Coreから利用する能力提供境界とする。

Providerは、ドメイン固有Operation、Repositoryアクセス、DBアクセス、検索、CRUD、外部サービス連携、
決定的なドメインロジックを提供する。実装方式はMCP、REST API、Local Serviceのいずれでもよく、Coreは
その違いを意識しない。現時点ではMCPを第一候補とするが、MCPには依存しない。

Providerは頭脳ではない。ユーザー意図の解釈、Provider / Operation選択、複数Providerの組み合わせ、
Clarification、Persona、会話、最終回答はLLM / Jarvis Core側の責務とする。Provider内部の決定的なdispatch、
Repository選択、外部API fallbackは許容するが、自然言語の意味判断に使わない。

Web UI、Chat、Voice、Camera、将来のAgentは、可能な限り同じProvider境界を利用する。write Operationは
入口やtransportにかかわらずRuntimeのValidation、Permission、Confirmation、Auditを迂回しない。

---

## Principle 19

Catalog is Declarative, Not Decision Logic

Operation、Capability、Dashboard Catalogは、利用可能な契約、能力説明、表示候補を宣言する。Catalogは
ユーザー発話を分類する判断表、Provider / Operation router、回答template、表示優先順位ではない。

ユーザー意図、Provider / Operation選択、複数能力の組み合わせ、最終回答、現在表示するDashboard候補は
LLM / Jarvis Coreが判断する。PythonはCatalog読込、schema validation、versioning、transport mapping、
principal / permission / visibilityの決定的filterを担えるが、keywordや固定ruleで意味判断しない。

Operation、Capability、Dashboard Catalogは目的が異なるため分離し、Catalog entryの存在を実装済み、認可済み、
Evidence、表示決定の意味に使わない。詳細は
[Catalog Principle / Guardrail](decisions/2026-07-catalog-principle.md)を参照する。

---

## Principle 20

Conversation Quality Without a Python Brain

会話品質は、Conversation Context、prior turns、Observationのprovenance / visibility / limitations / freshness、
Provider Operation契約、Capability説明、Memory、LLM promptを改善して上げる。Pythonへ自然言語keyword分岐、
話題判定、Provider / Operation選択、Clarification、固定fallback回答を追加して上げてはならない。

Conversation Quality Testは自然な会話の評価であると同時に、Pythonへ意味判断が戻ることを防ぐRegression Guardとする。
改善対象と禁止対象の区別は、[Conversation Quality / Python Brain Regression GuardのImprovement Target Principle](decisions/2026-07-conversation-quality-python-brain-regression-guard.md#improvement-target-principle)を参照する。

---

## Principle 21

Observation Is Observed Facts, Not Interpretation

ObservationはProvider実行結果から決定的に確認できるfactsと、その`visibility`、`freshness` / `observed_at`、
`limitations`、`provenance`だけをLLMへ渡す。意図、話題、解釈、次Action、推薦、回答、Provider / Operation選択、
UI表示判断を含めない。詳細は[Observation Guardrail](decisions/2026-07-observation-guardrail.md)を参照する。

---

## Principle 22

Observation Reference Principle

**Observation = conversational evidence, not cached truth.**

Observationは、この会話で取得した事実を取得時点の証拠として参照するものであり、現在値を保証するキャッシュではない。

現在の真実はProviderから取得する。Observationだけで十分か、Providerを再実行するかはLLMが判断する。
PythonはObservationの保存、visibility、size制限、redactionを担うが、stable / volatile / freshness判定によって
再取得を判断しない。

詳細は[Observation Reference Principle](decisions/2026-07-observation-reference-principle.md)を参照する。

---

## Principle 23

Memory Is Long-term Knowledge, Not Truth

**Memory = long-term useful knowledge, not truth.**

Memoryは、好み、呼び方、家族構成、継続中プロジェクト、長期設定、明示的な記憶依頼など、会話終了後も
長期的に有用になり得る知識だけを扱う。現在の予定、今日取得した写真や旅行一覧、Observation、Entity Context、
Provider結果をMemoryとして保持しない。現在の状態はDomain Providerから取得する。

Memoryの採用、Provider再取得、ObservationからMemory候補への昇格はLLMが判断する。Pythonは保存、更新、削除、
visibility、retention、redactionに限定し、重要度、推薦、意味的な検索順位、要約、回答、Provider / Operation選択、
keyword / topic判定を担わない。

詳細は[Memory Principle / Responsibility Boundary](decisions/2026-07-memory-principle.md)を参照する。
