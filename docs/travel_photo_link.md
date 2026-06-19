# Travel Photo Link

## 目的

この文書は、Travel SkillとPhoto Skillの接続部分を整理する。

TravelとPhotoは分離するが、旅行の振り返りやSpotごとの写真表示では連携が必要になる。

連携は、Travelが写真を所有する形ではなく、Travelの文脈からPhotoへ問い合わせる形にする。

---

## 分離する理由

TravelとPhotoを分離する理由:

* Travelは旅行計画、移動、予約、持ち物、予算、レビューを扱う
* Photoは写真Asset、Album、Search、Thumbnail、Immich Adapterを扱う
* 写真は旅行だけでなく、日常、家族、イベントでも使う
* Immichの都合をTravelに持ち込むと、旅行設計が写真サービスに依存する
* TravelをMCP Tool化する時に、写真基盤の詳細を隠せる
* Photo側でプライバシー、閲覧権限、サムネイル取得を一貫管理できる

Travelは「旅行に関連する写真を見たい」と要求する。

Photoは「条件に合う写真候補」を返す。

---

## 接続モデル

TravelとPhotoの接続は、IDの直接所有ではなく、関連候補として扱う。

主な接続:

* `trip_id` と `asset_id`
* `spot_id` と `asset_id`
* `trip_id` と `album_id`
* `spot_id` と位置情報
* 旅行期間と撮影日時

Travel側の主キーとPhoto側の主キーは別物である。

片方のDB設計や外部サービスIDが変わっても、もう片方に影響を広げない。

---

## trip_id と asset_id

`trip_id` と `asset_id` の関係は、旅行全体と写真Assetの関連を表す。

利用例:

* このTrip期間中に撮影された写真を表示する
* このTripのReviewに使う写真候補を出す
* このTripに関連するAlbum候補を探す
* 家族に共有してよい写真だけを表示する

関連付けの方法:

* 明示的に紐づけられたAsset
* 旅行期間から推定されたAsset
* 旅行先の位置情報から推定されたAsset
* Trip用Albumに含まれるAsset

明示リンクと推定リンクは区別する。

推定リンクは、ユーザー確認前に確定データとして扱わない。

---

## spot_id と asset_id

`spot_id` と `asset_id` の関係は、特定の訪問地点と写真Assetの関連を表す。

利用例:

* Spot詳細に、その場所で撮影された写真候補を表示する
* 旅行後にSpotごとの振り返りを作る
* 子どもが楽しんでいたSpotの写真を探す
* 再訪したいSpotの思い出を確認する

関連付けの方法:

* Spotの位置情報と写真のGPS情報を比較する
* Spot訪問予定時刻と撮影日時を比較する
* ユーザーが明示的に写真をSpotへ紐づける

Spot代表画像としてGoogle Places画像を使う場合、それはPhoto Assetではない。

Google Places画像はTravelとGoogle Places Adapterの責務であり、Immich写真とは別に扱う。

---

## 時刻ベース候補

時刻ベース候補は、旅行期間やSpot訪問予定時刻から写真候補を探す方法である。

例:

* Trip開始日時から終了日時までのAssetを候補にする
* Spot滞在予定時刻の前後数時間に撮影されたAssetを候補にする
* 移動中の写真はMove時間帯の候補として扱う

注意点:

* カメラやスマートフォンの時刻ずれがあり得る
* タイムゾーンを考慮する
* 家族メンバーごとに撮影端末が違う
* 時刻だけではSpotを確定できない

時刻ベース候補は便利だが、確定リンクではない。

---

## 位置ベース候補

位置ベース候補は、Spotの緯度経度と写真AssetのGPS情報を使って写真候補を探す方法である。

例:

* Spot中心から一定距離内で撮影されたAssetを候補にする
* Tripの目的地エリア内で撮影されたAssetを候補にする
* 複数Spotが近い場合は撮影時刻と組み合わせて候補を絞る

注意点:

* 写真にGPS情報がない場合がある
* 屋内や地下では位置精度が落ちる
* 近接Spotでは誤判定が起きる
* 家族の位置情報はプライバシー上の配慮が必要である

位置ベース候補も、ユーザー確認前は推定として扱う。

---

## 明示リンクと推定リンク

TravelとPhotoのリンクには2種類ある。

* 明示リンク: ユーザーまたはToolが確定した関連
* 推定リンク: 時刻、位置、Album、タグから推定した関連

明示リンクはTripやSpotの表示に安定して使える。

推定リンクは候補表示、Review作成支援、Album提案に使う。

将来DB化する場合も、`confidence` や `source` を持たせ、推定理由を説明できる形にする。

---

## Tool候補

接続に関するTool候補:

* `travel.find_related_photos`
* `photo.find_assets_for_trip`
* `photo.find_assets_for_spot`
* `photo.link_asset_to_trip`
* `photo.link_asset_to_spot`
* `photo.suggest_assets_for_trip`
* `photo.suggest_assets_for_spot`

更新系のリンク操作は、家族写真の見え方に影響するため確認と監査を必要とする。

---

## 権限とプライバシー

TravelとPhotoの接続では、以下に注意する。

* Trip参加者だけが見られる写真がある
* 子どもの写真は共有範囲を慎重に扱う
* 位置情報は生活圏や行動履歴を推測できる
* 旅行写真に家族以外が写ることがある
* 推定リンクを自動公開しない

初期実装では、読み取り候補の提示を中心にする。

Album作成、共有、明示リンク確定などは更新系として扱い、Runtimeの確認と監査を通す。
