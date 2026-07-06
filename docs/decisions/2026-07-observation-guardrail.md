# Decision: Observation Guardrail

## 日付

2026-07-06

## Status

Accepted

## 背景

Observation Envelopeにより、Providerの実行結果をLLMが利用しやすいfactsとして渡せる。Travel / Photoで
決定的集計の有効性を確認した一方、Observationへ意味判断や次Actionを入れると、ProviderまたはRuntimeが
LLMとは別の頭脳になる。Observationを会話文やPresentation Contractとして流用することも同じ境界違反を招く。

## 決定

**Observation = observed facts, not interpretation.**

Observationは、実行時に観測された結果と、その利用条件を表す構造化データである。解釈、判断、次Action、回答、
表示決定は含めない。同じ構造化結果から同じ値を得られる決定的変換・集計だけをfactsとして許可する。

## 許可する内容

Observationには次を含めてよい。

* `count`、`date_range`、`bucket_counts`
* boolean facts
* `source`、`status`
* `freshness`、`observed_at`
* `limitations`、`visibility`、`provenance`
* `raw_result`
* raw resultに対する決定的metadata集計

具体例は`trip_count`、`titles`、`date_bucket_counts`、`has_location_count`、`has_faces_count`、
`provider_count`、`capability_count`である。これらも取得結果、認可されたmetadata、Catalogから機械的に確認できる
場合に限る。名称がfacts風でも、意味推論や非決定的分類で生成した値は許可しない。

## 禁止する内容

Observationには次を含めてはならない。

* user intent、topic
* `next_action`、`recommended_operation`
* `recommended_answer`、final answer text、clarification text
* priority、insight、emotion、interpretation
* guess、assumption、recommendation
* UI presentation decision、card selection
* provider selection、operation selection

禁止例は`next_operation: get_trip`、`recommended_answer: 兵庫県は3回です`、`topic: travel`、
`insight: 家族のおでかけが多い`、`should_show_card: true`、`priority: high`である。これらはfactsではなく、
LLM / Jarvis Coreまたは将来のPresentation Contractが扱う判断である。

## 責務境界

### Provider

Providerは自分の実行結果から、決定的factsを生成してよい。意味解釈、ユーザー意図、次Action、Provider / Operation
選択、回答生成を行わない。

### Runtime / Agent Host

Runtime / Agent HostはObservation Envelopeを組み立て、`visibility`、`limitations`、`provenance`、
`freshness` / `observed_at`を付与する。schema、size、permission、visibility等の決定的policyは適用できるが、
結果の意味や会話上の価値を判断しない。

### LLM / Jarvis Core

LLM / Jarvis CoreはObservationを材料として、意味解釈、十分性評価、会話、推論、Clarification、次Action、
最終回答を行う。Observationのstatusや存在だけで事実の十分性を自動確定しない。

### UI

Presentation Contractが定義されるまでは、UIはObservationからカード表示、カード種別、優先順位を判断しない。
Observationのfield追加をUI presentation decisionの代替にしない。

## Privacy / Safety

ObservationはLLMへ渡るため、次を必須とする。

* 目的に必要な最小限だけを開示し、principalに応じた`visibility`を適用する。
* `freshness`または`observed_at`を持たせ、古いObservationを現在の事実として扱わせない。
* 欠落、部分取得、検索範囲、Provider error等を`limitations`に残す。
* `provenance`で出所とOperationを追跡可能にする。
* `raw_result`は正本結果の保持を理由に無制限転送しない。秘密、不要な本文、画像・音声本体、過剰な個人情報を
  redaction / size制限なしにLLMへ渡さない。
* 家族写真、位置、顔、予定、在宅情報は高注意情報として扱い、最小開示、permission、visibility、retentionを
  個別に確認する。

ObservationであることはEvidenceの完全性、認可、鮮度、または安全性を保証しない。利用時にmetadataとRuntime policyを
併せて評価する。

## Python Brain Regression Guardとの関係

ObservationはLLMへの材料を改善する正しい対象だが、材料という名前でPython判断を埋め込めば
Python Brain Regressionになる。レビューではfield名だけでなく生成過程を確認し、「raw resultから決定的に再現できる
観測事実か」「LLMの解釈・選択・回答を先回りしていないか」を問う。Provider Brainも同じ違反として扱う。

## 影響

次に実装してよいのは、Observation schema / size validation、`observed_at`、`visibility`、`limitations`、
`provenance`の一貫した付与、決定的metadata集計、redaction、Privacy test、禁止fieldと生成経路のreview / testである。

まだ実装してはならないのは、Observationによるtopic / intent分類、Provider / Operation推薦、次Action、回答文、
Clarification、insight / priority、カード選択、意味scoreや推測値である。Presentation Contractが採用されるまで、
ObservationをUI判断契約として拡張しない。

## Jarvis Principle Check

1. Web UIから利用できるか: Web ChatはCore経由で安全なObservationを利用できるが、UIカード判断には使わない。
2. API / Toolとして利用できるか: Runtime経由のProvider Operation結果にChannel非依存で適用できる。
3. 将来MCP Tool化できるか: MCP adapterも同じfactsとmetadata境界を維持し、直接Provider実行や選択判断を行わない。
4. Jarvis Coreから呼び出せるか: CoreはObservationを単一LLM Agent Loopの判断材料として利用する。
5. UI依存のロジックになっていないか: ObservationとPresentation Contractを分離する。
6. 読み取り系か更新系か: 本Decisionはdocsのみで、対象契約は主に実行結果の読み取り表現である。
7. 副作用・権限・プライバシー上の注意: LLM転送前の最小開示、visibility、鮮度、制約、provenance、redactionが必要である。
