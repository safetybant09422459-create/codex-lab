# Travel Photo Link

## 目的

この文書は、Travel SkillとPhoto Skillの接続部分を整理する。

TravelとPhotoは分離するが、旅行やおでかけのMemory、Spotごとの写真表示、Cover Imageの家族写真置き換えでは連携が必要になる。

連携は、Travelが写真を所有する形ではなく、Travelの文脈からPhotoへ問い合わせる形にする。

Travel Web UIのExperience Card原則では、全面画像、体験タイトル、時刻、参加者、メモが組み合わさって、旅行前は計画のワクワク感、旅行後はMemoryとしての振り返りを作る。詳細は[Travel UI Experience Principle](travel_ui_experience.md)に置く。

この見た目はWeb UI向けであり、Photo Link、MCP Tool、Chat、APIに時計アイコンや中央タイトルなどの表示を強制しない。ただし、Photo Linkや関連APIは、UIがExperience CardやMemory画面を再現できるだけの写真候補、Cover Image参照、撮影時刻、関連するSpot / Timeline Item情報を返せる必要がある。

---

## 分離する理由

TravelとPhotoを分離する理由:

* TravelはTrip / Outing、Candidate Spot、Spot、Move、Event、Memo、Cover Image、Memoryを扱う
* Photoは写真Asset、Album、Search、Thumbnail、Immich Adapterを扱う
* 写真は旅行だけでなく、日常、家族、イベントでも使う
* Immichの都合をTravelに持ち込むと、旅行設計が写真サービスに依存する
* TravelをMCP Tool化する時に、写真基盤の詳細を隠せる
* Photo側でプライバシー、閲覧権限、サムネイル取得を一貫管理できる

Travelは「旅行に関連する写真を見たい」と要求する。

Photoは「条件に合う写真候補」を返す。

Google Places由来の仮画像はPhoto Assetではない。Spot代表画像やTrip代表画像としてGoogle仮画像を使う場合、取得とローカル保存はTravel + Google Places Adapter側で扱う。家族が撮影した写真に置き換える場合だけ、Photo SkillのAsset参照をTravelが採用する。

---

## 接続モデル

TravelとPhotoの接続は、IDの直接所有ではなく、関連候補として扱う。

主な接続:

* `trip_id` と `asset_id`
* `spot_id` と `asset_id`
* `move_id` と `asset_id`
* `event_id` と `asset_id`
* `memory_id` と `asset_id`
* `trip_id` と `album_id`
* `spot_id` と位置情報
* 旅行期間と撮影日時

Travel側の主キーとPhoto側の主キーは別物である。

片方のDB設計や外部サービスIDが変わっても、もう片方に影響を広げない。

---

## trip_id と asset_id

`trip_id` と `asset_id` の関係は、旅行全体と写真Assetの関連を表す。

利用例:

* このTrip / Outing期間中に撮影された写真を表示する
* このTripのMemoryに使う写真候補を出す
* このTripに関連するAlbum候補を探す
* 家族に共有してよい写真だけを表示する
* 「去年の旅行ハイライト」に使う写真候補を探す

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
* Experience CardのCover Imageを家族写真へ置き換える候補を探す

関連付けの方法:

* Spotの位置情報と写真のGPS情報を比較する
* Spot訪問予定時刻と撮影日時を比較する
* ユーザーが明示的に写真をSpotへ紐づける

Spot代表画像としてGoogle Places画像を使う場合、それはPhoto Assetではない。

Google Places画像はTravelとGoogle Places Adapterの責務であり、Immich写真とは別に扱う。

Spot代表画像を実際の家族写真に置き換える場合は、Photo SkillのAsset候補から選んだ参照をTravelのCover Imageに採用する。置き換えずGoogle仮画像のまま残してもよい。

---

## move_id / event_id と asset_id

`move_id` と `asset_id`、`event_id` と `asset_id` の関係は、場所ではなく時間帯や出来事から写真Assetを探すための接続である。

利用例:

* 新幹線の移動中に撮った写真を表示する
* 飛行機や予約済み交通の時間帯に撮った写真を候補にする
* 「お家出発！」のようなEventに近い写真を候補にする
* Event自体には写真がないが、Memory作成時に近い時間帯の写真を探す

関連付けの方法:

* Moveの予定/実績時間と撮影日時を比較する
* Eventの予定/実績時刻の前後を候補にする
* ユーザーが明示的に写真をMoveやEventへ紐づける

MoveやEventの写真リンクは、位置情報よりも時刻ベースの推定が中心になる。

---

## memory_id と asset_id

`memory_id` と `asset_id` の関係は、思い出メモと写真Assetの関連を表す。

Memoryは単なるReviewではなく、以下の組み合わせである。

* 思い出メモ
* その時の写真
* 時刻
* 体験タイトルまたは表示タイトル
* 子どもの反応
* もう一度見たい場面

利用例:

* Spot滞在時間から写真候補を出し、Memoryに採用する
* Move時間帯の写真をMemoryに採用する
* 「去年の旅行ハイライト」に使うMemoryと写真を選ぶ
* 家族写真に置き換えたCover ImageをMemoryにも関連付ける

Memoryに紐づく写真は、明示リンクを優先する。推定リンクは候補表示に留め、共有前に確認する。

写真、メモ、時刻、体験タイトルが揃っている場合、Spot / Timeline Item自体がMemoryとして機能することがある。その場合もPhoto Linkは、別Memory EntityだけでなくSpot、Move、Event、Timeline Item相当の文脈へ接続できるようにする。

---

## 時刻ベース候補

時刻ベース候補は、旅行期間やSpot訪問予定時刻から写真候補を探す方法である。

例:

* Trip開始日時から終了日時までのAssetを候補にする
* Spot滞在予定時刻の前後数時間に撮影されたAssetを候補にする
* 移動中の写真はMove時間帯の候補として扱う
* Event時刻の前後に撮影されたAssetを候補にする

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

推定リンクは候補表示、Memory作成支援、Album提案に使う。

将来DB化する場合も、`confidence` や `source` を持たせ、推定理由を説明できる形にする。

Photo Linkのsource例:

* `time_range`
* `location`
* `album`
* `manual`
* `cover_image_replacement`

Photo Linkのowner例:

* `trip`
* `spot`
* `move`
* `event`
* `memory`

---

## Tool候補

接続に関するTool候補:

* `travel.find_related_photos`
* `photo.find_assets_for_trip`
* `photo.find_assets_for_spot`
* `photo.find_assets_for_time_range`
* `photo.link_asset_to_trip`
* `photo.link_asset_to_spot`
* `photo.link_asset_to_memory`
* `photo.suggest_assets_for_trip`
* `photo.suggest_assets_for_spot`
* `travel.create_memory`
* `travel.replace_cover_image_with_photo`

更新系のリンク操作は、家族写真の見え方に影響するため確認と監査を必要とする。

---

## 権限とプライバシー

TravelとPhotoの接続では、以下に注意する。

* Trip参加者だけが見られる写真がある
* 一緒に行ったTrip / Outingだけをじいじばあばに見せたい場合がある
* 子どもの写真は共有範囲を慎重に扱う
* 位置情報は生活圏や行動履歴を推測できる
* 旅行写真に家族以外が写ることがある
* 推定リンクを自動公開しない
* Cover Imageとして採用された家族写真も共有範囲の対象になる

初期実装では、読み取り候補の提示を中心にする。

Album作成、共有、明示リンク確定、Cover Imageの家族写真置き換えなどは更新系として扱い、Runtimeの確認と監査を通す。

---

## Photo Link v0.1設計メモ

v0.1では、Experience詳細の候補写真を追加読み込みできるようにし、明示リンク保存は次段階に分ける。

理由:

* 現在のDBは`SQLiteTravelStorage.initialize()`で`CREATE TABLE IF NOT EXISTS`を直接実行する方式で、差分migrationの方針が未整備である
* 明示リンク保存は更新系であり、確認、監査、権限、共有範囲の扱いを同時に決める必要がある
* 候補写真のページネーションは読み取り系で、Photo Skill境界を壊さず先に安全に導入できる

次段階で追加するテーブル候補:

```sql
CREATE TABLE travel_experience_photo_links (
    id TEXT PRIMARY KEY,
    experience_id TEXT NOT NULL,
    photo_asset_id TEXT NOT NULL,
    link_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT
);
```

`link_type`はまず以下を想定する。

* `linked`: このExperienceの写真として明示確定
* `cover_candidate`: Cover Image候補
* `hidden`: このExperience候補から非表示

API候補:

* `GET /api/travel/experiences/{experience_id}/photos?limit=20&offset=0`
* `POST /api/travel/experiences/{experience_id}/photo-links`
* `DELETE /api/travel/experiences/{experience_id}/photo-links/{link_id}`

保存系APIは、Runtime確認とauditを通し、Photo Assetの公開範囲をTravel側表示に持ち込まない。
