# Photo Skill

> 2026-06-27実装同期: ChatGPT Projectへの新規アップロードでは `04_photo_skill_current.md` を正とする。このファイルは背景・詳細設計版として残す。Travel側のExperience Photo Link、cover、期間外検索は実装済みである。

## 目的

Photo Skillは、家族の写真を扱うSkillである。

旅行写真だけでなく、日常写真、家族写真、イベント写真を含めて、写真Asset、Album、Search、Thumbnail、Immich連携を管理する。

TravelはPhotoを利用することがあるが、PhotoはTravel専用ではない。

## 扱う対象

Photoが扱う対象:

* Asset
* Album
* Search
* Thumbnail
* Immich Adapter
* 写真メタデータ
* 表示権限

Photoは、写真の所在、検索、表示、外部写真サービスとの接続を担当する。

## 責務

Photoの責務:

* 写真Assetを参照・管理する
* Albumを参照・管理する
* 撮影日時、位置情報、人物、タグなどで写真を検索する
* Thumbnail / Previewを取得する
* Immich APIとの通信をImmich Adapterとして扱う
* ImmichのAsset ID、Album ID、メタデータをJarvis向けに正規化する
* 旅行写真と日常写真を同じ写真基盤で扱う
* Travelからの写真候補要求に応答する
* Memory作成やCover Image置き換えに使う写真候補を返す
* 写真に関するプライバシーと権限境界を管理する

## 非責務

Photoが扱わないもの:

* Tripの作成・更新
* Experience / Spot / Move / Eventの作成・更新
* Travel Memoryの意味づけ
* Spot代表画像としてのGoogle Places画像管理
* Trip代表画像としてのGoogle Places画像管理
* Google Places API呼び出し
* 旅行計画の意思決定
* Calendar予定管理
* Navigation経路管理

「旅行として何を意味する写真か」はTravel側の文脈で判断する。Photoは写真基盤として、検索結果、Asset、Thumbnail、権限情報を返す。

## Travelとの境界

Travelは写真を必要とする場合にPhotoへ問い合わせる。

例:

* Trip期間中に撮影された写真を探す
* Spot周辺で撮影された写真を探す
* MoveやEventの時間帯に撮影された写真を探す
* Travel Memoryに使う写真候補を取得する
* Google仮画像を家族写真へ置き換える候補を取得する
* Tripに紐づくAlbum候補を取得する
* 家族に共有してよい写真だけを取得する

Photoが返すもの:

* `asset_id`
* `album_id`
* thumbnail URL
* preview URL
* 撮影日時
* 位置情報
* 人物・タグなどのメタデータ
* 表示可能かどうかの権限情報

PhotoはTripやSpotの意味を所有しない。Travelが`trip_id`、`timeline_item_id`、`memory_id`などを持ち、Photoはそれに対する写真候補を返す。

Google Places由来の仮画像はPhoto Assetではない。Photoが扱うのは家族が撮影した写真、Immich Asset、Album、Thumbnailである。

## Immich Adapter

Immich AdapterはPhoto Skillの内部Adapterである。

担当:

* Immich Asset取得
* Immich Album取得
* Immich Search呼び出し
* Immich Thumbnail / Preview取得
* Immich APIレスポンスの正規化
* Immich固有IDとJarvis側IDの対応
* APIキーや接続設定の隠蔽
* エラー処理とレート制御

TravelはImmich Adapterを直接呼ばない。

将来Immich以外の写真基盤に移行しても、Travelの設計を変えずに済むようにする。

## 標準アーキテクチャ

```text
Runtime
↓
Permission / Confirmation / Audit
↓
ExecutorRegistry
↓
PhotoExecutor
↓
PhotoRepository
↓
ImmichAdapter
↓
Immich API
```

PhotoRepositoryをPhoto Skillの中心にする。

PhotoExecutorの責務:

* Tool入力をPhotoRepository呼び出しへ変換する
* Repository結果をTool応答JSONへ整形する

PhotoRepositoryの責務:

* Asset、Album、Search、Thumbnailのドメインロジックと正規化
* ImmichAdapterの隠蔽
* Jarvis向けの写真結果形式を作る

ImmichAdapterの責務:

* Immich API
* 認証
* レスポンス正規化
* エラー処理
* レート制御

禁止:

* TravelからImmichAdapterやImmich APIを直接呼ばない
* UIに写真検索やAlbum判断のドメインロジックを書かない
* PhotoExecutorにImmich API詳細を書きすぎない
* Album作成、共有、削除などの更新系をRuntimeなしで実行しない

## 実装済みTool

現在のTool定義:

* `get_photos`
  * `skill_id: photo`
  * `mode: read`
  * `risk_level: medium`
  * `confirmation_required: false`
  * `audit_required: true`
  * required: `from`, `to`
* `get_asset`
  * `skill_id: photo`
  * `mode: read`
  * `risk_level: medium`
  * `confirmation_required: false`
  * `audit_required: true`
  * required: `asset_id`

現在の補助API:

* `GET /api/photo/assets/{asset_id}/thumbnail`
* `GET /api/photo/assets/{asset_id}/preview`

## 将来のTool候補

読み取り:

* `photo.search_assets`
* `photo.get_asset`
* `photo.get_thumbnail`
* `photo.list_albums`
* `photo.get_album`
* `photo.find_assets_by_time_range`
* `photo.find_assets_near_location`
* `photo.find_assets_for_trip`
* `photo.find_assets_for_spot`

更新:

* `photo.create_album`
* `photo.add_assets_to_album`
* `photo.suggest_album_for_trip`
* `photo.update_asset_visibility`
* `photo.share_album`

初期は読み取り系から始める。Album作成、Asset追加、共有、削除などは家族写真のプライバシーに影響するため、Permission / Confirmation / Auditを通す。

## 検索とリンク

PhotoはTravelから以下のような条件を受け取る。

* Time range
* Location
* Album
* Person / tag
* Trip期間
* Spot周辺
* Event前後

返す写真候補には、推定理由やconfidenceを持たせるのが望ましい。

Travel側で明示リンクとして採用されるまでは、推定リンクを確定扱いしない。

## リスク分類

Photo Skill全体は`mixed`かつ`medium risk`で扱う。

読み取りでも家族写真、位置情報、子ども情報が含まれるため、low riskにしすぎない。

更新系は少なくともmedium、共有や削除はhigh候補である。

## プライバシー注意

* 家族写真を無断で共有しない
* 子どもの写真は特に慎重に扱う
* 位置情報付き写真を外部へ送らない
* 推定リンクを確定情報として扱わない
* Thumbnail URLやPreview URLの公開範囲に注意する
* Immich APIキーをUIやログへ出さない

## Jarvis Principle Check

1. Web UIから利用できるか: Photo画面、Travel写真候補、Jarvis Screenで利用できる。
2. API / Toolとして利用できるか: `get_photos`、`get_asset`、Thumbnail / Preview APIで利用できる。
3. 将来MCP Tool化できるか: PhotoRepositoryを中心にすれば可能。
4. Jarvis Coreから呼び出せるか: CoreはRuntimeまたはPhoto API経由で呼び出せる。
5. UI依存のロジックになっていないか: 写真検索と正規化はRepository / Adapterに置く。
6. 読み取り系か更新系か: 現在はread中心。将来Album作成や共有はwrite。
7. 副作用・権限・プライバシー上の注意はあるか: 家族写真、子ども、位置情報、共有範囲、Immich APIキーに注意する。
