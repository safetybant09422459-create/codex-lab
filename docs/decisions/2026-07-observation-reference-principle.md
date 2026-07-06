# Decision: Observation Reference Principle

## 日付

2026-07-06

## Status

Accepted

## 背景

Observation Guardrailにより、Observationは観測事実であり、解釈、推論、次Action、回答ではないと定めた。
一方、過去のObservationを現在値のキャッシュとして扱うと、取得後に変化した正本を確認せず、過去の事実を
「今も正しい」と誤認する。Observationを保持する目的と、現在の真実を取得する責務を分離する必要がある。

## 決定

**Observation = conversational evidence, not cached truth.**

Observationは「この会話で、その時に取得した事実」を保持する会話中の証拠である。最新情報を保持する責務はなく、
Providerが現在の真実（Source of Truth）を取得する。Observationは再利用（Reuse）するものではなく、取得時点の
証拠として参照（Reference）する。

## 責務境界

### Conversation State

Conversation Stateは会話履歴を保持する。Observationを会話の文脈として保持できるが、現在値へ更新したり、
正本として扱ったりしない。

### Observation

Observationは、この会話で取得した事実と、`observed_at`、`provenance`、`limitations`等の利用条件を保持する。
「あの時取得した」という証拠であり、「今も正しい」という保証ではない。

### Provider

Domain ProviderはRepository、外部API等の正本境界から現在の真実を取得する。最新情報が必要な場合は、LLMが
Provider Operationを選択してRuntime経由で再実行する。

### Memory

Memoryは長期記憶を扱う。会話中のObservationやDomain Providerの現在値を置き換えない。

## ReferenceとReuse

たとえば、ユーザーが「旅行一覧見せて」と依頼し、Observationに`trip_count`と`titles`が返った直後に
「それ何件？」と質問した場合、LLMは直前の取得結果についての質問だと判断し、そのObservationを参照して回答できる。

一方、30分後に再び「旅行一覧見せて」と依頼された場合、過去のObservationを現在の一覧として再利用してはならない。
LLMは依頼、会話文脈、`observed_at`、limitations等を評価し、現在値が必要ならProviderを再実行する。時間だけを
固定閾値として機械判定するのではなく、再取得の必要性はLLMが判断する。

## Pythonの責務

PythonがObservationについて担うのは、次の決定的処理である。

* Observationの保存
* visibilityの適用
* size制限
* redaction

Pythonは次を行ってはならない。

* データやOperationのstable / volatile判定
* freshness判定による再取得判断
* Observationのキャッシュとしての利用
* Providerを再取得するかどうかの判断
* 経過時間、過去Provider、field名等による意味的な再取得routing

`freshness`や`observed_at`の保存、検証、決定的な切り詰めは許可する。ただし、それらを閾値と照合してPythonが
Provider再実行を選択してはならない。

## LLM / Jarvis Coreの責務

LLM / Jarvis Coreは次を担う。

* Observationを会話中の証拠として参照する。
* Observationだけで依頼に十分か判断する。
* 現在値や追加Evidenceが必要ならProvider Operationを選択し、Runtime経由で再実行する。
* Observationだけで十分なら不要なProvider呼び出しを行わない。

Observationの存在、status、`freshness`、`observed_at`だけから「今も正しい」と推論してはならない。

## Observation Guardrailとの違い

[Observation Guardrail](2026-07-observation-guardrail.md)は、Observationに何を入れてよいかを規定する。
すなわち、観測事実は許可し、解釈、意図、次Action、回答、表示判断を禁止する。

本Decisionは、正しい観測事実をいつ・どの意味で使えるかを規定する。Observationは取得時点の会話証拠であり、
現在値を保証するキャッシュではない。内容が事実であっても、過去のObservationから現在の真実を確定してはならない。

## Python Brain Regression Guardとの関係

再取得の必要性は会話意図、依頼対象、時間的文脈、必要な確度を評価する意味判断である。Pythonがstable / volatile分類、
freshness閾値、過去Provider等から再取得を決めると、会話判断がPythonへ戻り、Python Brain Regressionになる。

PythonはObservationを安全に保存・転送する決定的基盤に留まり、十分性評価とProvider再実行の選択を単一LLM Agent
Loopへ残す。これは不要なProvider呼び出しを常に強制する原則でもない。参照だけで十分か、再取得が必要かをLLMが判断する。

## 影響

Observation store、Conversation State、Context Assemblyを将来拡張するときも、cache hit、TTL、stable flag、
volatile flag等でProvider呼び出しを省略・強制する意味判断を追加しない。Observationの保持期間やsize制限は、
privacy、resource budget、retentionの決定的policyとして扱い、現在値の保証とは分離する。

## Jarvis Principle Check

1. Web UIから利用できるか: Web ChatもCore経由でObservationを会話証拠として参照できる。
2. API / Toolとして利用できるか: Chat APIとProvider OperationのChannel非依存な境界に適用できる。
3. 将来MCP Tool化できるか: MCP経由でも過去Observationを現在値キャッシュにせず、必要な再実行はLLMが選択する。
4. Jarvis Coreから呼び出せるか: CoreはObservationをLLM contextへ渡し、選択されたOperationをRuntimeへ接続する。
5. UI依存のロジックになっていないか: 参照・再取得判断はUIではなく単一LLM Agent Loopが担う。
6. 読み取り系か更新系か: 本Decisionはdocsのみで、対象は主に会話証拠とProvider readの責務分離である。
7. 副作用・権限・プライバシー上の注意: 保存時のvisibility、size、redaction、retentionと、再取得時のRuntime認可を守る。
