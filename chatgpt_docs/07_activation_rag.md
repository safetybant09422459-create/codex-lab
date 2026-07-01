# Activation RAG Handoff

更新日: 2026-06-30

## 最重要定義

Activation RAGは、Jarvisが現在の発話に関係しそうな正本Entityを軽く思い出すための索引である。

> DBを思い出すための索引。DBの代替ではない。

Repositoryが唯一のSource of Truthである。RAG Document、alias、tag、embedding、metadata、ranking結果は
すべて非正本であり、破棄・再生成できなければならない。

## 現在の実装

PoCとして次がある。

* Provider中立な共通RAG Document
* in-memory lexical index
* Travel Provider / Builder
* Chat Routerへのread-only候補注入
* 検索障害時にBasic Chatを継続するfallback

未実装:

* 永続indexとincremental lifecycle
* Memory / Photo / Calendar Provider
* Knowledge Enrichment連携
* Capability Usage RAG
* Provider横断の完成したEntity Resolution

## 責務境界

```text
Repository (canonical entities)
  -> Provider
  -> Builder
  -> regenerable RAG Documents
  -> Search index
  -> unverified candidates
  -> Entity Resolution
  -> Repository canonical re-read
  -> Evidence / Runtime
```

Activation RAGが行うこと:

* 認可scope内で候補を広く軽く検索する
* Provider横断の共通候補envelopeを返す
* score、matched terms、ranking reason等を診断可能にする
* timeout、空結果、部分障害をChatから分離する

Activation RAGが行わないこと:

* Entityの最終確定
* 回答用の正本提供
* Tool / Actionの実行許可
* Permission、Confirmation、Audit、Validation
* Domain DBの更新

## Travel Providerの意味

Travelは最初のcontract test / PoCであり、Activation RAG全体の設計対象ではない。Trip、Experience、地域、
日付、place等の語彙やmetadataはTravel Provider / Builderが所有する。CoreへTravel固有field、entity type
列挙、alias辞書、ranking ruleを追加しない。

将来Provider候補:

* Memory: 承認済みMemoryの参照候補
* Photo: Asset / Album等の参照候補
* Calendar: Eventの参照候補
* Garden: Garden Entity / recordの参照候補

Homeの「テレビをつける」等は現実世界へ作用するActionであり、Entity想起Providerと同じ設計にしない。

## Entity Resolutionとの境界

検索候補は未検証hintである。Entity Resolverは候補を正本へ結び、現在も存在するか、認可されているか、
質問対象として一意かを確認する。

* 0件: 推測で補完せず、必要なら聞き返す。
* 1件: 単一候補だけを理由に確定せず、Repositoryで再取得する。
* 複数件: 自動選択せず、Evidenceに基づく候補提示または追加文脈で解決する。
* stale / deleted / visibility mismatch: 候補を棄却し、indexを失効・再構築できるようにする。

## Knowledge Enrichmentとの境界

Knowledge Enrichmentは検索Documentを育てる。Domain Entity本体は育てない。

```text
conversation / failed search / ambiguous result / user correction
  -> Learning Event（必要最小限）
  -> alias / tag / relation / search-document candidate
  -> review / approval / rejection
  -> approved projection
  -> RAG Document rebuild
```

候補にはsource、source_ref、confidence、status、visibility、lifecycleを持たせる。ユーザー修正は強い
signalだが、即座にDomain factにはしない。本体DBの変更は別のDomain writeとしてRuntimeを通す。

## Capability Usage RAG

Entityを思い出す索引とは別に、Skill / Toolの使い方を思い出すcorpusを将来検討する。

* 「テレビつけて」 -> Home Action
* 「神戸で何した？」 -> Travel
* 「写真ある？」 -> Photo

Capability Catalogを置き換えず、承認済み利用例による選択補助とする。Action ToolとMemory Searchは
別設計であり、検索上位を実行許可にしない。現時点では実装しない。

## 実装優先順位

1. Activation RAG Core
2. Travel Provider改善
3. Entity Resolution
4. Knowledge Enrichment
5. Memory Provider
6. Photo Provider
7. Calendar Provider
8. Capability Usage RAG検討

## 設計時の禁止事項

* RAG indexをSource of Truthにする。
* RAGだけから削除済みEntityや本体DBを復元する。
* 検索scoreでEntity確定、権限、確認、Runtimeを省略する。
* Travel固有ロジックをCore契約へ入れる。
* Enrichmentから本体DBへ自動書き戻す。
* 検索後にだけvisibility filterをかける。
* ActionとMemory / Domain Searchを同一視する。

## Jarvis Principle Check

1. Web UIから利用できるか: Chat API経由で利用可能。専用UIを必須にしない。
2. API / Toolとして利用できるか: Core serviceとして利用可能。公開時も結果は候補に限定する。
3. 将来MCP Tool化できるか: 共通request / result、認証、visibility、purposeを保てば可能。
4. Jarvis Coreから呼び出せるか: Context Assembly / Entity Resolutionのread-only補助として呼び出す。
5. UI依存のロジックになっていないか: Provider、Builder、SearchはUI非依存である。
6. 読み取り系か更新系か: 検索はread。index更新は派生projection更新でありDomain更新ではない。
7. 副作用・権限・プライバシー上の注意: Domain副作用は禁止。検索前認可、最小送信、失効、監査が必要。
