# Gift Skill

## 目的

Giftは、プレゼント候補と、家族が贈った・もらった記録を長期的な正本として残すSkillである。
単なる買い物リストではなく、「誰から誰へ」「いつ」「どのイベントで」という家族の関係と記憶を、
後からJarvisが会話で参照できる構造化Evidenceにする。

## v0.1でできること

* プレゼント候補の登録
* 贈った記録、もらった記録の登録
* 誰から・誰へ、日付、任意金額、メモ、関連イベント、記念日の保存
* 種類、人、年による決定的な絞り込み
* Web UI、Consumer API、Runtime Tool、Jarvis Core Observationからの利用

写真、購入、通知、人物関係の推測、推薦文生成は行わない。候補から購入済みへの遷移、編集、archiveも将来範囲である。

## アーキテクチャ

```text
Web / Chat / future MCP
  -> Gift Provider Operation
  -> Runtime Permission / Confirmation / Audit
  -> GiftExecutor
  -> GiftRepository
  -> SQLiteGiftStorage
  -> storage/gift.db
```

正本schemaは`migrations/gift/001_initial.sql`。起動時にidempotentに適用し、
`gift_schema_migrations`へversion 1を記録する。Travel DBとは分離し、Giftの変更で旅行データを危険にさらさない。

## Operation

### `gift.list_gifts`

read / low risk。`entry_type`、`person`、`year`で絞り込める。Observationは保存済み事実だけを返し、
関係、意図、次の贈り物をProviderやPythonで推測しない。

### `gift.create_gift`

write / medium risk / confirmation required / audit required。候補はtitleだけで保存できる。
贈った・もらった履歴はgiver、recipient、gift_dateを必須とする。

現在のWeb writeは、保存ボタン、ブラウザ確認、server-owned `admin + confirmed` でRuntimeへ入る。
本格的なユーザー認証やConfirmation Transactionではないため、信頼できるローカル環境限定の暫定境界である。
インターネットへ直接公開してはならない。

## Privacy

Gift履歴は、家族関係、記念日、嗜好、金額を含むprivate family dataである。将来household/member principalを導入し、
候補を贈る相手本人から隠すsurprise visibilityも明示契約にする。LLMへ渡す場合は質問に必要な最小件数へ制限する。

## 将来

* edit / archiveと、候補から贈答履歴への明示遷移
* Calendarの誕生日・記念日へのID参照
* Photo Assetへの明示リンク
* Shoppingへの購入候補引き渡し
* AIによる候補提案。ただし保存済みEvidenceを提示し、Pythonで推薦しない
* MCP Resource / Tool化
