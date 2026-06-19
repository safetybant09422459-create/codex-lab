# Travel Skill

## 目的

Travel Skillは、家族旅行の計画、実行、振り返りを扱うSkillである。

旅行に関する意思決定、移動、予約、持ち物、予算、メモを整理し、Jarvisが家族の旅行準備を手伝える状態にする。

Travelは写真そのものを管理しない。旅行中や旅行後に写真を利用することはあるが、写真の保存、検索、サムネイル生成、Immich連携はPhoto Skillに委譲する。

---

## 扱う対象

Travelが扱う主な対象:

* Wishlist
* Trip
* Participants
* Spot
* Move
* Reservation
* Checklist
* Packing
* Budget
* Memo
* Review

これらは「旅行という体験」を構成する情報であり、家族が旅行前、旅行中、旅行後に確認・更新する対象である。

---

## 責務

Travelの責務:

* 行きたい場所をWishlistとして管理する
* Tripを作成し、日程、目的地、参加者を整理する
* 旅行に参加する家族メンバーをParticipantsとして扱う
* 訪問候補や訪問済み地点をSpotとして管理する
* Spot間の移動予定をMoveとして管理する
* ホテル、交通、レストラン、チケットなどのReservationを管理する
* 出発前のChecklistを管理する
* 家族ごとのPacking項目を管理する
* 旅行予算と実績をBudgetとして管理する
* 旅行中の気づきや注意点をMemoとして残す
* 旅行後の感想、再訪したい場所、反省点をReviewとして残す
* Spot代表画像としてGoogle Places Adapterから取得した画像を利用する
* 旅行に関連する写真が必要な場合、Photo Skillへ問い合わせる

家族旅行では、単に場所を並べるだけでは不十分である。

子どもの体力、移動時間、休憩、荷物、予約確認、天気、写真の振り返りまで含めて、Travelは「旅行が成立するための情報」を扱う。

---

## 非責務

Travelが扱わないもの:

* 写真Assetの保存
* 写真Albumの管理
* 写真検索エンジン
* サムネイル生成
* Immich APIとの通信
* Immich Albumの作成・更新
* 家族写真全体の分類
* Google Places APIの直接呼び出し
* Google Places画像キャッシュの実装詳細
* Calendar全体の予定管理
* Navigation全体の経路探索
* Weather全体の天気管理

Travelは、旅行に必要な外部情報を利用することはある。

ただし、写真、天気、地図、予定、通知などの横断的な領域をTravel内に抱え込まない。

---

## Photoとの関係

TravelはPhotoを利用する側である。

例:

* このTripに関連する写真を取得したい
* このSpot周辺で撮影された写真を探したい
* この旅行期間中の写真を候補として表示したい
* 旅行Reviewに使う写真候補を出したい

TravelがPhotoへ渡す情報:

* `trip_id`
* `spot_id`
* 旅行期間
* Spotの位置情報
* 参加者
* 検索条件

TravelがPhotoから受け取る情報:

* `asset_id`
* thumbnail URL
* 撮影日時
* 位置情報
* album候補

TravelはPhotoの内部実装を知らない。PhotoがImmichを使うか、ローカルDBを使うか、将来別サービスへ移るかはTravelの責務外である。

---

## Google Places Adapterとの関係

TravelはSpot候補やSpot代表画像のためにGoogle Places Adapterを利用する。

Travelが必要とするもの:

* 場所候補検索
* Place詳細
* Place画像
* 代表画像URLまたはキャッシュ済み画像参照

TravelはGoogle Places APIを直接呼ばない。

APIキー、レート制限、画像キャッシュ、レスポンス正規化、エラー処理はGoogle Places Adapterが担当する。

---

## 将来のTool候補

Travel SkillのTool候補:

* `travel.create_wishlist_item`
* `travel.list_wishlist_items`
* `travel.create_trip`
* `travel.update_trip`
* `travel.add_participant`
* `travel.add_spot`
* `travel.search_spot_candidates`
* `travel.set_spot_cover_image`
* `travel.add_move`
* `travel.add_reservation`
* `travel.list_reservations`
* `travel.add_checklist_item`
* `travel.complete_checklist_item`
* `travel.add_packing_item`
* `travel.assign_packing_item`
* `travel.add_budget_item`
* `travel.summarize_budget`
* `travel.add_memo`
* `travel.create_review`
* `travel.find_related_photos`

読み取り系と更新系は分けて定義する。

予約、予算、参加者、子どもの情報を扱うToolは、家族プライバシーと権限確認を前提にする。

---

## 将来のExecutor候補

Travel Executor候補:

* `TravelReadExecutor`
* `TravelWriteExecutor`
* `TravelPlanningExecutor`
* `TravelReservationExecutor`
* `TravelPhotoLinkExecutor`
* `TravelPlaceAdapterExecutor`

初期実装では、読み取りやstub実行から始める。

更新系Toolは、RuntimeのPermission Engine、Confirmation Engine、Audit Logを通す。

---

## MCP化した場合の活用例

TravelをMCP Tool化すると、Jarvis Coreや外部AIクライアントから旅行情報を安全に利用できる。

活用例:

* 「次の家族旅行の予定をまとめて」
* 「岡山から子ども連れで無理のない移動計画を作って」
* 「旅行前日に必要な持ち物を確認して」
* 「予約漏れがないか見て」
* 「旅行後に写真候補と一緒に振り返りを作って」

MCP Tool化する場合も、TravelはPhotoやGoogle Placesの実装詳細を隠す。

Jarvis Coreから見るTravelは「旅行の状態を扱うTool」であり、写真管理サービスやGoogle APIの薄いラッパーではない。

---

## 設計メモ

Travelは家族旅行の文脈を持つ。

同じSpotでも、家族旅行では以下が重要になる。

* 子どもが楽しめるか
* 移動が長すぎないか
* 休憩できるか
* 雨の日でも成立するか
* 予約が必要か
* 荷物が増えすぎないか
* 写真を後で振り返りやすいか

この文脈をTravelに残し、写真管理や外部Place APIの詳細は別責務に分ける。
