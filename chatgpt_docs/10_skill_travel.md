# Travel Skill

## 目的

Travel Skillは、家族旅行、日帰りのおでかけ、近場イベントを含む「家族のおでかけ記憶」を扱うSkillである。

単なる旅行管理ではなく、Trip / Outing、候補、体験、写真との関係、思い出、予定と実績の差分を扱い、Jarvisが家族の計画と振り返りを手伝える状態にする。

Skill名は現時点ではTravelのままとする。ただしTripは宿泊旅行だけでなく日帰りのおでかけも含む。

## 核心

TravelはFamily Outing Memory Skillである。

核になるEntity:

* Trip / Outing
* Experience
* Experience Type: `spot`, `move`, `event`, `memo`
* Timeline Item
* Candidate Spot
* Cover Image
* Photo Link
* Memory
* Participants

Packing、Budget、Checklist、Souvenir、Reservationは補助機能であり、現時点の核ではない。

## 概念

### Trip / Outing

家族旅行、日帰りおでかけ、近場イベント、後から振り返る思い出整理を束ねる単位である。

宿泊旅行に限定しない。

例:

* マリンワールド日帰り
* 近所の公園で朝散歩
* じいじばあばと誕生日会
* 去年の夏の思い出整理

### Experience

Trip / Outingの中に時系列で並ぶ家族の体験である。Travelの主概念である。

場所だけが思い出ではない。移動中にも写真やメモは残る。Google Placesにも写真にも紐づかない出来事も家族の記憶になる。

Experience Type:

* `spot`: 場所と関係し得る体験。物理Placeそのものではない
* `move`: 移動中の体験
* `event`: 出発、到着、チェックイン、家族内の節目などの出来事
* `memo`: Timeline上に置く短い記録や注意

### Timeline Item

DB / 既存互換上の保存実体名である。

domain / API / MCP / Toolでは原則Experienceと呼ぶ。既存DBや互換ToolではTimeline Itemという名前を残す。

v0.1では`travel_timeline_items`をExperienceの保存実体として活かす。

### Timeline View

Experienceを時刻や`order_no`で並べた取得/表示結果である。

TimelineはUI専用ロジックではない。Jarvis CoreやMCP Toolからも同じExperienceをTimelineとして取得できるようにする。

## 正規用語

| 文脈 | 正規名 | 補足 |
| --- | --- | --- |
| domain / API / Tool / MCP | Experience | Trip内の家族の体験 |
| DB / 既存互換 | Timeline Item | `travel_timeline_items`の保存実体 |
| UI | タイムライン、体験、スポット、移動、メモ | 文脈に応じて使い分ける |

旧語彙:

* `place_spot`は`spot`へ寄せる
* `experience`はtype名ではなく概念名
* `item_type`は既存互換名として残し、domain / API / MCPでは`experience_type`と呼ぶ

## 責務

Travelの責務:

* 行きたい場所をWishlistとして管理する
* Trip / Outingを作成し、タイトル、日程、都道府県、参加者を整理する
* 同じ時間帯に並ぶ未確定候補をCandidate Spotとして管理する
* 訪問候補、採用済み地点、訪問済み地点、行かなかった地点を`spot` Experienceとして管理する
* 移動予定や移動実績を`move` Experienceとして管理する
* Google Placesや写真に紐づかない出来事を`event` ExperienceとしてTimelineに置けるようにする
* Timeline上で見せたい短い記録を`memo` Experienceとして管理する
* Trip代表画像とExperience代表画像をCover Imageとして扱う
* 写真が必要な場合、Photo Skillへ問い合わせる
* Google仮画像を、実際の家族写真へ置き換えた参照を保持する
* 旅行後のMemoryを作るための文脈を保持する

## 非責務

Travelが扱わないもの:

* 写真Assetの保存
* Immich APIとの直接通信
* サムネイル生成
* 家族写真全体の分類
* Google Places APIの直接呼び出し
* Google Places画像キャッシュの実装詳細
* Calendar全体の予定管理
* Navigation全体の経路探索
* Weather全体の天気管理
* 家計簿全体の管理
* 日常タスク全体の管理

写真、天気、地図、予定、通知などの横断領域をTravel内に抱え込まない。

## Candidate Spot

計画時には、同じ時間帯に複数のSpot候補が並ぶ。

例:

* 10:00 海遊館
* 10:00 レゴランド
* 10:00 通天閣

これは重複データではなく、家族で相談するための未確定計画である。

状態例:

* `candidate`
* `planned`
* `confirmed`
* `visited`
* `skipped`
* `cancelled`
* `unplanned`

候補は削除、採用、時間変更、別時間帯への移動ができる前提にする。旅行当日まで`candidate`のまま残ってもよい。

## Planned / Actual

Travelでは予定と実績を分ける。

共通フィールド候補:

* `planned_start_at`
* `planned_end_at`
* `actual_start_at`
* `actual_end_at`
* `planned_note`
* `actual_note`
* `status`
* `source`
* `confidence`

これによりJarvisは旅行後に「予定との差分」と「次回への学び」を説明できる。

例:

* 予定より水族館に長く滞在した
* 昼食候補は混雑で行けなかった
* 予定外に公園へ寄った
* 移動時間が想定より長く、次回は休憩を増やすべき

## v0.1中心Entity

v0.1で必須Entity:

* Trip
* Timeline Item / Experience
* Photo Link
* Participant
* Trip Participant
* Cover Image参照

v0.1で必須にしないもの:

* Packing
* Budget
* Reservation
* Checklist
* 汎用Place

## Relationship

```text
Wishlist
  |
  | promote / convert
  v
Trip / Outing
├ Participants
├ Experience
│  ├ Photo Link
│  ├ Cover Image Ref
│  ├ Memo
│  └ Memory
├ Reservation
├ Checklist
├ Packing
├ Budget
└ Review

Timeline View = Experienceを時刻とorderで並べたView
```

v0.1ではSpot、Move、Event、Memoを別テーブルに分けず、Experience / Timeline Itemに統合する。

理由:

* 実データ上、SpotがPlaceではなくExperienceとして使われている
* 移動中も写真や思い出メモを持てる
* Timeline表示、Tool応答、Memory生成では共通フィールドが多い
* 初期実装で過剰な正規化を避けられる

## DBフィールド候補

### `travel_trips`

重要フィールド:

* `id`
* `title`
* `start_date`
* `end_date`
* `prefectures`
* `outing_type`: `overnight_trip`, `day_trip`, `short_outing`, `event`
* `status`: `draft`, `planning`, `confirmed`, `in_progress`, `completed`, `cancelled`
* `cover_image_id`
* `memo`
* `privacy_level`: `private`, `family`, `shared`
* `created_by`
* `created_at`
* `updated_at`

`start_date` / `end_date`は必須にしない。思い出整理では日付不明があり得る。

`prefectures`は配列で持つ。複数県移動を許容する。

### `travel_timeline_items`

重要フィールド:

* `id`
* `trip_id`
* `item_type`
* `display_title`
* `place_name`
* `place_id`
* `category`
* `start_at`
* `end_at`
* `time_kind`: `planned`, `actual`, `estimated`, `unknown`
* `status`
* `cover_image_id`
* `memo`
* `order_no`
* `archived_at`
* `created_at`
* `updated_at`

`display_title`は体験として表示するタイトル。`place_name`は物理的な場所名や検索用の補助情報である。

## Tool方針

Canonical Tool:

* `travel.create_experience`
* `travel.get_experience`
* `travel.update_experience`
* `travel.archive_experience`

Alias / UI shortcut:

* `travel.add_spot`
* `travel.add_move`
* `travel.add_memo`

既存互換:

* `travel.create_timeline_item`
* `travel.get_spot`
* `travel.get_spot_photos`

Aliasは本流ではない。内部では`experience_type`を指定したCanonical Toolへ寄せる。

削除は物理削除ではなく、`archived`状態または`archived_at`による論理アーカイブを基本にする。

## 実装済みTravel Tool

読み取り:

* `get_trips`
* `get_trip`
* `get_trip_timeline`
* `get_spot`
* `get_trip_photos`
* `get_spot_photos`

更新:

* `create_trip`
* `create_timeline_item`
* `set_trip_cover_image`
* `set_spot_cover_image`

Travel writeは原則:

* `mode: write`
* `risk_level: medium`
* `confirmation_required: true`
* `audit_required: true`
* `admin`かつ`confirmed: true`のみ実行

## Repository構造

```text
Runtime
↓
Permission / Confirmation / Audit
↓
ExecutorRegistry
↓
TravelExecutor
↓
TravelRepository
↓
SQLiteTravelStorage
↓
storage/travel.db
```

`storage/travel.db` が新Travelの正である。

既存の `/mnt/nas/projects/project/travel.db` はLegacy Dataであり、移行元、参照元、サンプルとして扱う。TravelExecutorやUIがLegacy DBへ直接依存してはいけない。

TravelRepositoryの責務:

* Trip / Timeline Itemを取得・保存する
* Timeline ItemをExperience Cardとして再現できる情報に正規化する
* Storage差し替えを隠蔽する
* UI専用ではなくTool / API / MCPでも使える戻り値にする
* PhotoやGoogle Placesは抽象化されたAdapter / Repository経由で扱う

## Photoとの関係

TravelはPhotoを利用する側である。

TravelがPhotoへ渡す情報:

* `trip_id`
* `spot_id` / `timeline_item_id`
* 旅行期間
* Spotの位置情報
* 参加者
* 検索条件

Photoから受け取る情報:

* `asset_id`
* `album_id`
* thumbnail URL
* preview URL
* 撮影日時
* 位置情報
* 表示可能かどうかの権限情報

TravelはPhotoの内部実装を知らない。PhotoがImmichを使うか、将来別サービスへ移るかはTravelの責務外である。

Google Places由来の仮画像はPhoto Assetではない。家族写真へ置き換える場合だけ、Photo SkillのAsset参照をTravelのCover Imageとして採用する。

## Photo Link

TravelとPhotoのリンクには2種類ある。

* 明示リンク: ユーザーまたはToolが確定した関連
* 推定リンク: 時刻、位置、Album、タグから推定した関連

推定リンクは候補表示、Memory作成支援、Album提案に使う。ユーザー確認前に確定データや共有対象にしない。

source例:

* `time_range`
* `location`
* `album`
* `manual`
* `cover_image_replacement`

## Google Places Adapterとの関係

現時点ではPlace Skillを作らない。

Google PlacesはTravelが必要とする場所検索、場所詳細、場所画像、画像キャッシュをAdapterとして扱う。

TravelはGoogle Places APIを直接呼ばない。

Adapterが担当する操作:

* `search_place_candidates`
* `get_place_details`
* `get_place_photos`
* `cache_place_photo`

APIキー、課金、レート制限、画像キャッシュ、レスポンス正規化、エラー処理はAdapterが担当する。

Place Skill化は、Travel以外の複数SkillがPlace検索や共通Placeモデルを必要とした時に再検討する。

## UI Experience Principle

Travel Web UIでは、現行アプリのTimelineカード体験を失わない。

Experience Cardで大切なもの:

* 全面画像
* 中央に大きく表示される体験タイトル
* 左上の時計アイコン
* 時刻表示
* 縦に並ぶタイムラインカード
* 旅行前はワクワクする計画画面
* 旅行後は思い出を振り返るMemory画面

これはWeb UI向けの表示原則であり、MCP Tool、Chat、APIに見た目を強制しない。ただしTool/APIはUIが再現できるだけのデータを返す。

必要なデータ:

* `title`
* `display_title`
* `start_time`
* `end_time`
* `cover_image`
* `experience_type`
* `participants`
* `memo`
* `linked_photos`
* `place_name`
* `status`
* `planned_start_at`
* `actual_start_at`

## Memory

Memoryは単なるReviewではない。

Memoryに含むもの:

* 思い出メモ
* その時の写真
* 時刻
* 体験タイトル
* 子どもの反応
* また行きたい理由
* もう一度見たい場面

十分な情報を持つExperienceは、それ自体がMemoryとして機能する場合がある。独立Memory Entityは、共有範囲、複数写真、独立要約、ハイライト選択が必要になった時に使う。

## 権限とプライバシー

Travelは家族の行動、位置、写真、参加者、共有範囲を扱う。

注意:

* 子どもの写真を自動公開しない
* 推定Photo Linkを確定扱いしない
* 共有範囲変更は確認と監査を必要とする
* 旅行計画や参加者情報の更新はwrite / medium risk以上で扱う
* 外部APIへ送る情報は最小限にする

## Jarvis Principle Check

1. Web UIから利用できるか: Travel画面でTrip、Timeline、写真候補、Memoryを表示できる。
2. API / Toolとして利用できるか: Runtime Toolとして読み取りとguarded writeを提供できる。
3. 将来MCP Tool化できるか: Experience中心のTool境界にすれば可能。
4. Jarvis Coreから呼び出せるか: CoreはRuntime経由でTravel Toolを呼び出せる。
5. UI依存のロジックになっていないか: Experience CardはUI表現であり、正はExperience / Repositoryに置く。
6. 読み取り系か更新系か: mixed。初期はread中心、作成・更新・共有・Cover Image設定はwrite。
7. 副作用・権限・プライバシー上の注意はあるか: 旅行計画、位置、写真、参加者、共有範囲は確認と監査を前提にする。
