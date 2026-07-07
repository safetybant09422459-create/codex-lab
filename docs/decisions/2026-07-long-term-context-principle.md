# Decision: Long-term Context Principle

## 日付

2026-07-07

## Status

Accepted. [Memory Principle / Responsibility Boundary](2026-07-memory-principle.md)の内部概念名と責務定義を置き換える。

## 背景

「Memory」は保存機構やDBを連想させ、Jarvisが推論時に何を判断材料とすべきかという本質を曖昧にする。
必要なのは保存方式の設計ではなく、会話を越えて未来の推論へ影響する文脈の責務を定めることである。

## 決定

**Long-term Context = context that should change future reasoning over a long period.**

Jarvisの推論入力を次の6区分で捉える。

* User Input
* Conversation Context
* Observation
* Long-term Context
* Provider Results
* Capability Catalog

Long-term Contextは、呼び方、長期的な好み、判断基準、家族との関係、継続プロジェクト、設計思想などを扱う。
Record、Observation、Conversation State、ProviderのSource of Truthではない。その役割は、未来の推論を変える
長期文脈をLLMへ提供することに限る。

失敗、ユーザー訂正、頓珍漢な回答、選択ミス、Runtime失敗等はユーザー理解ではないため、Long-term Contextへ
保存しない。これらは[Jarvis Self-Improvement Principle](2026-07-jarvis-self-improvement-principle.md)に従い、
Jarvis改善専用のLearning Logとして分離する。

### Providerとの責務分離

Providerは出来事、記録、状態、操作対象、すなわち「What happened」を管理する。Long-term Contextは、
その文脈によって「Why future reasoning should change」をLLMへ伝える。Providerは世界を管理し、
Long-term Contextはユーザー理解を支える。

Long-term Contextの一部は、将来Domain Providerへ構造化され得る。ただし基準は件数、保存量、永続化の都合ではない。
構造化によって新しい検索、新しい操作、新しい能力が生まれる場合に限る。

### Observationとの責務分離

Observationは今回の会話で得た取得時点の事実であり、現在の会話証拠である。Long-term Contextは会話を越えて
継続的に有効な文脈である。Observationを保存しただけではLong-term Contextにならない。

### Retrieval Principle

Long-term Contextは唯一、件数が無制限に増え得る推論入力であるため、全件をLLMへ渡さない。visibility、permission、
token budgetを満たす候補だけをretrievalによってLLMへ渡す。

Pythonはvisibility、permission、token budgetと候補retrievalまでを担う。候補の意味的な採否、組み合わせ、
推論への反映はLLMが判断する。Pythonに意図判断、重要度判定、回答生成、Provider / Operation選択を置かない。

## 理由

この境界により、保存技術を先に固定せず、LLMへ与える判断材料としてLong-term Contextを設計できる。
また、Providerの正本性、Observationの会話証拠、Conversation Contextの短期継続性と混同せず、Python Brainを
再導入せずにJarvisの継続的なユーザー理解を育てられる。

## 非対象

* Provider、DB、Graph DB、SQLiteの設計
* retrieval algorithm、embedding、RAGの実装詳細
* API、Tool、Pythonコードの追加または変更
* 保存、更新、削除の具体契約

## 再検討条件

Long-term Contextの候補取得または利用が、LLM / Python責務境界、token budget、visibility、permissionを
満たせない具体例が得られた場合に再検討する。保存方式の選定だけを理由に原則は変更しない。

## Jarvis Principle Check

1. Web UIから利用できるか: 将来の入口になり得るが、本DecisionはUIを規定しない。
2. API / Toolとして利用できるか: 今回は能力や契約を追加しない。
3. 将来MCP Tool化できるか: Provider化で新能力が生じる場合に別途判断する。
4. Jarvis Coreから呼び出せるか: CoreがLLM入力へ候補を組み立てる概念として利用する。
5. UI依存のロジックになっていないか: なっていない。
6. 読み取り系か更新系か: 今回は設計文書のみ。推論時の利用は候補の読み取りである。
7. 副作用・権限・プライバシー上の注意: 長期的な家族文脈を含み得るため、最小開示、visibility、permission、token budgetが必要。
