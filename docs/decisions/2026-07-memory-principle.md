# Decision: Memory Principle / Responsibility Boundary

## 日付

2026-07-06

## Status

Superseded by [Long-term Context Principle](2026-07-long-term-context-principle.md). 本文は旧判断の履歴として残す。

## 背景

JarvisにはConversation State、Observation、Entity Context、Domain Providerがある。長期知識を加える際、
Provider結果やObservationを長期保存する仕組み、現在値cache、Pythonによる重要度・推薦・検索順位付けとして
Memoryを実装すると、各責務とPython Brain Regression Guardを破壊する。

## 決定

**Memory = long-term useful knowledge, not truth.**

Memoryは会話終了後も保持する長期知識だけを扱う。好み、呼び方、家族構成、継続中プロジェクト、長期設定、
明示的に覚えるよう依頼された内容は対象になり得る。今日の旅行一覧、今日取得した写真、現在の予定、Observation、
Entity Context、Provider結果はMemoryとして保持しない。

責務を次のように固定する。

* Conversation State: 今回の会話
* Observation: この会話で取得した、取得時点の証拠
* Entity Context: 今回の会話で参照可能なEntity候補
* Domain Provider: 現在のSource of Truthへの能力境界
* Memory: 長期的に有用と思われる知識

Memoryは真実ではない。現在状態が必要ならDomain Providerを利用する。Memoryを採用するか、Providerを呼ぶか、
ObservationとMemoryをどう使い分けるか、ObservationをMemory候補にするかはLLMが判断する。

Python / Memory Providerは保存、更新、削除、visibility、retention、redactionと、Runtimeの決定的安全処理だけを
担当する。重要度判定、推薦、意味的な検索順位付け、意味要約、回答生成、Provider / Operation選択、keyword判定、
topic判定、ObservationからMemoryへの自動昇格判断は禁止する。

Memoryの作成、更新、visibility変更、削除、forgetはwriteであり、Validation、Permission、Confirmation、Auditを
迂回しない。Memory本文は監査や外部AI Model Providerへ過剰に複製・送信しない。

## 理由

この境界により、取得時点の証拠、現在の正本、会話内候補、短期会話状態、長期知識のlifecycleと信頼区分を分離できる。
また、Memoryによる会話品質改善をLLMへの材料改善として扱い、Pythonに第二の意味判断系を作る回帰を防げる。

## 影響

* 既存のMemory設計にある重要度、推薦、ranking、要約のPython責務は採用しない。
* Memory Provider実装前にread / write、visibility、retention、redaction、forgetの契約を具体化する。
* Memory Contextにはprovenance、更新時刻、limitationsと「真実ではない」信頼区分を含める。
* 現在状態への質問はMemoryだけで確定せず、LLMが必要に応じてDomain Providerを選択する。
* 本Decisionは設計のみであり、Memory Provider、DB、Tool、Chat挙動を実装しない。

詳細は[Jarvis Memory Principle and Responsibility](../memory_architecture.md)を参照する。

## Jarvis Principle Check

1. Web UIから利用できるか: 将来、共通Memory Operationを通じて利用できる。今回はdocsのみ。
2. API / Toolとして利用できるか: read / guarded write Operationとして利用できる設計。
3. 将来MCP Tool化できるか: Runtime gateを維持するtransport中立契約なら可能。
4. Jarvis Coreから呼び出せるか: LLM Agent Loopが利用判断を担う形で呼び出せる。
5. UI依存のロジックになっていないか: なっていない。
6. 読み取り系か更新系か: 本変更はdocsのみ。将来Memoryはread / write双方。
7. 副作用・権限・プライバシー上の注意: 長期保持、家族間visibility、外部送信、訂正、forgetに厳格な認可と監査が必要。
