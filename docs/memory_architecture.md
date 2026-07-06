# Jarvis Memory Principle and Responsibility

## 目的

Memoryは、会話終了後も長期的に保持し、将来の会話で有用になり得る知識だけを扱う。
Memoryは現在の真実、会話履歴、Provider実行結果、Entity候補の保管場所ではない。本書はMemory Provider v0の
実装仕様ではなく、将来実装で越えてはならない責務境界を定める。

正本Decisionは[Memory Principle / Responsibility Boundary](decisions/2026-07-memory-principle.md)を参照する。

## Memory Principle

**Memory = long-term useful knowledge, not truth.**

Memoryは「長期的に有用と思われる知識」であり、現在の状態を保証するSource of Truthではない。Memoryに
現在状態らしい記述があっても、現在の状態を知る必要がある場合はDomain Providerから取得する。Memoryを採用するか、
Providerを呼ぶか、取得したObservationとどう使い分けるかはLLMが判断する。

保持してよい例:

* ユーザーの好み
* ユーザーやJarvisからの呼び方
* 家族構成
* 継続中のプロジェクト
* 長期設定
* ユーザーから明示的に覚えるよう依頼された内容

保持しない例:

* 今日の旅行一覧
* 今日取得した写真
* 現在の予定
* Observationそのもの
* Entity Contextそのもの
* Provider結果そのもの

明示的な記憶依頼も、認可、visibility、retention、redaction等の安全規則を免除しない。会話全文やProvider結果を
便宜的にMemoryへ複製しない。

## 5つの責務境界

| 領域 | 責務 | lifecycle | Source of Truthか |
| --- | --- | --- | --- |
| Conversation State | 今回の会話を継続する短期状態 | session終了や期限切れで破棄可能 | いいえ |
| Observation | この会話でProviderから取得した、取得時点の証拠 | 会話終了後に破棄可能 | 現在値の正本ではない |
| Entity Context | 今回の会話で参照可能な正本ID付きEntity候補 | 会話に従属し、候補のまま | いいえ |
| Domain Provider | Repository、DB、外部APIから現在の状態を取得・更新する能力境界 | ドメインごとの規則に従う | 現在状態の取得経路 |
| Memory | 会話を越えて保持する長期知識 | retention / forgetまで存続可能 | いいえ |

### Observationとの違い

Observationは「あの時取得した証拠」であり、Provider実行結果から決定的に再現できる観測事実を扱う。Memoryは
長期的に保持する知識であり、Observationの別名、履歴倉庫、現在値cacheではない。Observationは会話終了で消えて
よく、Memoryは会話終了後も残り得る。

ObservationをMemory候補として扱うか、Memoryへ保存する内容をどう表現するかはLLMが判断する。Pythonは
Observationの種類、keyword、topic、件数、freshness等から自動昇格を判断しない。保存後も、元Observationを
Memory本文や正本として扱わない。

### Conversation Stateとの違い

Conversation Stateは今回の発話、直近Action、Observation、active entitiesなど、会話を継続するための短期状態である。
Memoryはsessionを越える長期知識である。Conversation Stateの永続化はMemory化を意味せず、State全体をMemoryへ
保存しない。

### Entity Contextとの違い

Entity Contextは今回の会話でLLMが参照できるEntity候補である。候補のID、label、provenance等を持てるが、参照解決、
Entity確定、長期知識ではない。Entity ContextをMemoryへコピーせず、現在のEntity情報が必要ならDomain Providerから
正本を再取得する。

### Providerとの違い

Domain ProviderはRepository、DB、外部API等を隠蔽し、現在のSource of Truthへ到達する能力境界である。Memoryは
現在状態を提供するProvider結果の代替ではない。「今の予定」「現在の家の状態」「最新の写真」「今日の旅行一覧」等は
Memoryから確定せず、該当Providerを利用する。

Memoryを保存・取得する実装境界を将来Memory Providerと呼ぶ場合も、その保存内容が真実になるわけではない。
Memory Providerは保存管理のProviderであり、他Domain Providerの正本性を引き継がない。

## LLMとPythonの責務

LLMが担当する:

* 認可済みMemoryを読む
* Memoryを今回の回答に採用するか判断する
* 現在状態が必要ならDomain Providerを呼ぶ
* ObservationとMemoryの出所、時間、用途を使い分ける
* 何をMemoryとして保存・更新・削除するかを構造化Operationとして提案する
* ObservationをMemory候補にするか判断する

Python / Memory Providerが担当する:

* 選択済みMemory Operationのschema validationと決定的実行
* 保存、更新、削除
* principal / permissionに基づくvisibilityの決定的適用
* 明示されたretention policyの適用
* policyに基づく決定的redaction
* writeに対するPermission、Confirmation、Auditの適用

Python / Memory Providerに禁止する:

* Memoryの重要度判定
* Memoryの推薦
* Memoryの意味的な検索順位付け
* Memoryの意味要約
* Memoryからの回答生成
* Memoryに基づくProvider / Operation選択
* keyword判定、topic判定
* ObservationからMemoryへの自動昇格判断

Storageの主キー一致、明示filter、作成日時順などの機械的な取得は許容する。ただし、それをユーザー意図への関連度、
重要度、推薦へ読み替えない。意味検索や要約が将来必要になった場合は、LLM責務と安全境界を維持する別Decisionを先に
採用し、Pythonへ意味判断を埋め込まない。

## Privacy、Retention、Forget

Memoryは家族構成、好み、健康、位置、家庭事情など長期かつ高感度な情報を含み得る。少なくともsubject、owner、
visibility、created_at、updated_at、retention、source種別を追跡し、利用前と更新前にprincipal / permissionを検証する。

作成、更新、visibility変更、削除、forgetは副作用を持つwriteであり、RuntimeのValidation、Permission、Confirmation、
Auditを迂回しない。監査ログへMemory本文を過剰に複製しない。redactionは明示policyによる決定的変換に限定し、意味を
推測して伏せ字対象を選ばない。外部AI Model Providerへ渡すMemoryは目的に必要な最小限にする。

## Python Brain Regression Guardとの関係

Memoryは会話品質を上げる材料であり、Pythonに第二の頭脳を置く理由ではない。テストを通すためにMemoryのkeyword、
topic、重要度score、固定ranking、回答template、Provider選択ruleを追加してはならない。改善時は、LLMへ渡す
Memory契約、provenance、visibility、retention、prompt、評価を見直す。

レビューでは必ず「決定的な保存管理か、自然言語の意味判断か」を確認する。後者はLLMの責務である。詳細は
[Conversation Quality / Python Brain Regression Guard](decisions/2026-07-conversation-quality-python-brain-regression-guard.md)を
参照する。

## 今回の非対象

* Memory Provider、Tool、Repository、DB schema、indexの実装
* Memory検索・自動想起・自動保存
* prompt、Context Assembly、Chat挙動の変更
* retention期間、visibility model、redaction policyの具体値
* 既存Conversation State、Observation、Entity Contextのコード変更

## 今後の実装時の注意点

1. readとwriteをOperation単位で分け、writeはConfirmationとAuditを必須候補として設計する。
2. MemoryとObservation、Entity Context、Provider結果に別schemaと別lifecycleを持たせる。
3. 現在状態をMemoryから回答せず、LLMが必要に応じてDomain Providerを呼べる契約にする。
4. Pythonへ重要度、推薦、意味ranking、要約、keyword / topic判定を追加しない。
5. 明示的な記憶依頼、訂正、削除、forgetを扱い、subject本人と家族のvisibilityを分離する。
6. 生会話、Observation、Provider結果、高感度情報を無条件または重複して保存しない。
7. Contextへ渡す際はprovenance、更新時刻、limitationsを保持し、Memoryが真実ではないとLLMへ明示する。

## 関連文書

* [Jarvis Core Architecture](architecture.md)
* [Jarvis Principles](principles.md)
* [Domain Provider Contract](provider_contract.md)
* [Observation Guardrail](decisions/2026-07-observation-guardrail.md)
* [Observation Reference Principle](decisions/2026-07-observation-reference-principle.md)
* [Conversation Quality / Python Brain Regression Guard](decisions/2026-07-conversation-quality-python-brain-regression-guard.md)

## Jarvis Principle Check

1. Web UIから利用できるか: 将来、同じMemory Operationを使う確認・修正・forget UIを追加できる。今回はdocsのみ。
2. API / Toolとして利用できるか: read / guarded writeのMemory Operationとして設計可能。今回は未実装。
3. 将来MCP Tool化できるか: transport中立契約とRuntime gateを維持すれば可能。
4. Jarvis Coreから呼び出せるか: LLM Agent LoopがMemory利用とProvider再取得を判断する前提で呼び出せる。
5. UI依存のロジックになっていないか: なっていない。責務はCore、LLM、Runtime、Memory Providerへ分離した。
6. 読み取り系か更新系か: 設計文書の変更のみ。将来Memoryはread / writeの両方を持つ。
7. 副作用・権限・プライバシー上の注意: 長期保持と家族情報を扱うため、最小開示、visibility、retention、redaction、確認、監査、forgetが必要。
