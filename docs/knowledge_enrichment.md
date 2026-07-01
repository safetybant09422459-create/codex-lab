# Jarvis Knowledge Enrichment

> Enrichment候補の投影先となる共通Documentと現在のTravel索引は
> [Jarvis Core Activation RAG](activation_rag.md)を参照する。SQLite / Repositoryだけを真実、
> RAG Documentを再生成可能な索引、
> Enrichmentをsource / confidence / approval付きの索引改善として分離する。

## Purpose and boundary

Knowledge Enrichment Engineは、Raw DataとInteractionから検索・想起しやすい派生知識候補を作る
Core基盤である。Memoryとは別物である。

* **Memory**: 誰にとって何が重要か、好み、思い出、判断文脈を扱う
* **Knowledge Enrichment**: Entityをどう発見・同定・関連付けるかを支援する派生索引を扱う
* **Domain Skill**: SQLite / Repository境界でTrip、Experience、Photo、Calendar Event等の正本を所有する

例えば「神戸のアンパンマンミュージアム」と「まい初旅行」の関連は検索用のEntity link / alias候補
になり得るが、それだけで本人の重要な思い出というMemoryにはならない。

## Inputs and outputs

候補生成trigger:

* Travel data updated / Experience added / Photo added / Calendar imported
* Conversation finished
* Failed query / zero result / ambiguous result
* User correction / candidate selection / explicit rejection

生成候補:

* `alias`, `tag`, `inferred_location`, `region`, `search_term`
* `summary`, `highlight`, `relation`, `entity_link`
* `embedding`, `memory_candidate`, `enrichment_candidate`

会話ログは学習材料だが、発話全文を無条件に派生データへコピーしない。Learning Eventとして必要な
query、候補、結果、訂正、対象Entity、認証主体、visibility、source参照だけを最小限に記録する。

例:

```text
failed query: 神戸のアンパンマンミュージアム
user correction: それはまい初旅行だよ
candidate relation: query phrase -> trip:まい初旅行
candidate alias: 神戸アンパンマン -> experience:アンパンマンミュージアム
source: chat_failure + user_correction
confidence: medium
status: candidate
```

失敗、聞き返し、曖昧性、ユーザー修正をLearning Eventにすることで、同じ失敗を将来の検索改善に
使える。ただし会話からの推測を正データへ直接書き戻さない。

最小の関係は次の通りである。

```text
conversation / failed search / user correction
  -> alias candidate / tag candidate / search-document update candidate
  -> review and approval
  -> Activation RAG Document rebuild
```

Knowledge Enrichmentが本体DBを更新することは禁止する。Domain factの修正が必要な場合は、別の明示的
Domain writeとしてPermission、Confirmation、Auditを通す。

## Separate facts from derived data

AI生成情報はTravel等の本体レコードへ混ぜない。横テーブルまたは同等の独立Storeで、正データ、
派生値、出所、confidence、review状態を分離する。概念schemaは次を想定するが、今回はDBを作らない。

| field | meaning |
| --- | --- |
| `entity_type`, `entity_id` | 派生情報の対象 |
| `enrichment_type` | alias / tag / inferred_location / search_term / summary / relation等 |
| `value` | 派生値または構造化relation |
| `confidence` | 不確実性 |
| `source` | data_update / chat_failure / user_correction / photo / memory等 |
| `source_ref` | 再検証可能な根拠参照 |
| `status` | candidate / approved / rejected / auto_applied |
| `created_at`, `updated_at` | lifecycle |

初期運用は`candidate`生成までとする。承認済み候補だけを検索索引へ利用するか、限定的に候補scopeで
利用する。高confidenceの自動適用は、precision、取消、provenance、privacyを評価した将来判断とする。

## Processing flow

```text
Domain Event / Learning Event
  -> privacy and permission filter
  -> candidate extraction
  -> entity resolution against authorized data
  -> confidence and provenance assignment
  -> candidate store
  -> review / approval policy
  -> approved projection
  -> Provider BuilderによるRagDocument再生成
```

Enrichment処理はChat応答の成功条件にせず、応答後の非同期処理にできる境界とする。処理失敗で会話を
失敗させない。候補を検索に使った場合はmatched-byとsourceを追跡し、誤りをrejectedへ戻せるように
する。

## Privacy, safety, and lifecycle

* owner、visibility (`private` / `family` / `shared`)、子ども、健康、位置、写真の境界を派生データにも
  継承する。派生aliasやembeddingが元データより広く公開されてはならない。
* ユーザー修正は強いsignalだが、本人が他者の非公開情報を確定できるとは限らない。認可を再検証する。
* source削除、Forget、権限変更時に派生候補、embedding、索引projectionを失効・再計算できるようにする。
* Auditへ高感度本文やembeddingを複製せず、処理ID、policy結果、対象参照を中心に残す。
* EnrichmentからDomain本体への更新は別の明示的writeであり、Permission / Confirmation / Auditを通す。

## Relationship to current Travel search

現在の`TravelSearchExpansionProvider`は「神戸 -> 兵庫, 須磨」等の固定辞書と依頼suffix除去を持ち、
`TravelSearchIndex`は現在のTrip fieldsをrule-basedで検索する。これは限定されたTravel Adapter内の
fallbackとして有効だが、Experience、Photo、会話訂正、confidence、provenanceを継続的に結ぶ
Enrichment Engineではない。

将来はTravel Adapterが承認済みEnrichment projectionをSearchDocumentへ追加し、Coreはその語彙や
格納方式を知らない構成にする。Goal-aware PlanningやBasic Chatへ固定alias辞書を持ち込まない。

## Non-goals for this review

DB / table作成、embedding生成、会話ログ永続化、自動適用、Memory候補作成、既存Travelデータ更新は
今回行わない。
