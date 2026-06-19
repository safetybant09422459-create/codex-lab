# Photo Skill

## 目的

Photo Skillは、家族の写真を扱うSkillである。

旅行写真だけでなく、日常写真、家族写真、イベント写真を含めて、写真Asset、Album、Search、Thumbnail、Immich連携を管理する。

TravelはPhotoを利用することがあるが、PhotoはTravel専用ではない。

---

## 扱う対象

Photoが扱う主な対象:

* Asset
* Album
* Search
* Thumbnail
* Immich Adapter

Photoは、写真の所在、検索、表示、外部写真サービスとの接続を担当する。

---

## 責務

Photoの責務:

* 写真Assetを参照・管理する
* Albumを参照・管理する
* 撮影日時、位置情報、人物、タグなどで写真を検索する
* サムネイルを取得・生成・キャッシュする
* Immich APIとの通信をImmich Adapterとして扱う
* ImmichのAsset ID、Album ID、メタデータを正規化する
* 旅行写真と日常写真を同じ写真基盤で扱う
* Travelからの「この旅行に関連する写真を取得したい」という要求に応答する
* 写真に関するプライバシーと権限境界を管理する

Photoは写真を中心にしたSkillであり、旅行、予定、家電、天気などの文脈を主責務にしない。

---

## 非責務

Photoが扱わないもの:

* Tripの作成・更新
* Spotの作成・更新
* MoveやReservationの管理
* ChecklistやPackingの管理
* BudgetやReviewの管理
* Spot代表画像としてのGoogle Places画像管理
* Google Places API呼び出し
* 旅行計画の意思決定
* Calendar予定管理
* Navigation経路管理

Photoは写真の保存先や検索方法を担当する。

「旅行として何を意味する写真か」は、Travel側の文脈と接続して判断する。

---

## Travelとの関係

Travelは、旅行に関連する写真を必要とする場合にPhotoへ問い合わせる。

例:

* Trip期間中に撮影された写真を探す
* Spot周辺で撮影された写真を探す
* 旅行Reviewに使う写真候補を取得する
* Tripに紐づくAlbum候補を取得する
* 家族に共有してよい写真だけを取得する

Photoは以下を返す。

* `asset_id`
* `album_id`
* thumbnail URL
* 撮影日時
* 位置情報
* 人物・タグなどのメタデータ
* 表示可能かどうかの権限情報

PhotoはTripやSpotの意味を所有しない。

Travelが `trip_id` や `spot_id` を持ち、Photoはそれに対する写真候補を返す。

---

## Immich Adapter

Immich AdapterはPhoto Skillの内部Adapterである。

担当:

* Immich Asset取得
* Immich Album取得
* Immich Search呼び出し
* Immich Thumbnail取得
* Immich APIレスポンスの正規化
* Immich固有IDとJarvis側IDの対応
* APIキーや接続設定の隠蔽
* エラー処理とレート制御

TravelはImmich Adapterを直接呼ばない。

将来Immich以外の写真基盤に移行しても、Travelの設計を変えずに済むようにする。

---

## 将来のTool候補

Photo SkillのTool候補:

* `photo.search_assets`
* `photo.get_asset`
* `photo.get_thumbnail`
* `photo.list_albums`
* `photo.get_album`
* `photo.find_assets_by_time_range`
* `photo.find_assets_near_location`
* `photo.find_assets_for_trip`
* `photo.find_assets_for_spot`
* `photo.create_album`
* `photo.add_assets_to_album`
* `photo.suggest_album_for_trip`

写真閲覧は読み取り系が中心である。

Album作成やAsset追加は更新系であり、確認、権限、監査を必要とする。

---

## 将来のExecutor候補

Photo Executor候補:

* `PhotoReadExecutor`
* `PhotoSearchExecutor`
* `PhotoThumbnailExecutor`
* `PhotoAlbumExecutor`
* `ImmichAdapterExecutor`

初期段階では、Asset検索、Thumbnail取得、Album参照などの読み取り系から始める。

更新系は、家族写真のプライバシーに影響するため、RuntimeのPermission Engine、Confirmation Engine、Audit Logを通す。

---

## 設計メモ

Photoは家族の記録を扱う。

旅行写真はその一部であり、Photo全体をTravelの下に置くと、日常写真や家族写真の扱いがTravel文脈に引きずられる。

Photoを独立させることで、以下が可能になる。

* 家族写真をTravel以外でも利用できる
* Immich移行や写真基盤変更に強くなる
* 写真プライバシーをPhoto側で一貫管理できる
* Travelは旅行計画と旅行体験に集中できる
