# Travel Data Model

## 目的

この文書は、Travel Skill実装前に、Jarvis向けのTravelデータモデルを整理するための設計メモである。

既存旅行アプリのDBをそのまま正とせず、家族旅行、日帰りのおでかけ、近場イベントを含む「家族のおでかけ記憶」を扱うための理想モデルを先に定義する。

Travelは旅行文脈を持つデータを扱う。写真Asset、Immich、Google Places API、Calendar全体、Finance全体、Task全体はTravelの外に置く。

---

## 概念定義

Travel Skillは、Family Outing Memory Skillである。

Trip / Outingは、宿泊旅行だけでなく、日帰りのおでかけ、近場イベント、後から振り返る家族の思い出整理を束ねる単位である。

Experienceは、Trip / Outingの中に時系列で並ぶ家族の体験であり、Travelの主概念である。

Experience Type:

* `spot`: 場所と関係し得る体験
* `move`: 移動中の体験
* `event`: 出発、到着、チェックイン、家族内の節目などの出来事
* `memo`: Timeline上に置く短い記録や注意

場所だけが思い出ではない。移動中にも写真や思い出メモは残るため、Photo、Memo、Time、PlaceはすべてExperienceに紐づく補助情報として扱う。

DB / 既存互換ではTimeline Itemと呼び、既存`travel_timeline_items`を保存実体として活かす。domain / API / MCP / ToolではExperienceと呼ぶ。TimelineはExperienceを時刻や手動順序で並べたViewであり、保存実体そのものではない。

---

## 全体方針

Travelの主要データ:

* Wishlist
* Trip / Outing
* Participants
* Candidate Spot
* Experience
* Experience Type: spot, move, event, memo
* Timeline Item
* Reservation
* Memo
* Cover Image
* Photo Link
* Memory
* Checklist
* Packing
* Budget

基本方針:

* Tripを旅行またはおでかけ単位の中心にする
* Tripは宿泊旅行だけでなく日帰りのおでかけも含む。文書上はTrip / Outingと表現する
* Experience、Reservation、Memory、Checklist、Packing、Budgetは原則Tripにぶら下げる
* Experienceは物理的な場所だけでなく、家族のおでかけにおける体験を表現できるようにする
* Spotに強く紐づく情報も、v0.1では`experience_type = spot`のExperienceにぶら下げる
* 同じ時間帯の複数候補を`spot` Experienceの`candidate`状態として保持できるようにする
* TimelineはExperienceから生成できるようにする
* WishlistはTrip作成前の独立データとして扱える
* 旅行文脈に閉じる情報はTravelに置く
* 汎用化が必要になったら、将来Skill分離候補にする

Packing、Budget、Checklist、Souvenirは補助機能である。現時点の核は、Trip / Outing、Experience、Cover Image、Photo Link、Memoryである。

Web UIで失ってはいけないExperience Card原則は[Travel UI Experience Principle](travel_ui_experience.md)に置く。この原則はWeb UI向けであり、MCP Tool / Chat / APIに時計アイコンや中央文字などの見た目を強制しない。ただし、Tool/APIはUIが再現に使えるタイトル、表示タイトル、時刻、画像、参加者、メモ、写真リンクを返せる必要がある。

---

## Planned / Actual の考え方

Travelでは、予定と実績を分けて扱う。

同じExperienceでも、状態は変化する。

* 行きたい候補
* 採用済み
* 実際に行った
* 行けなかった
* 予定外に立ち寄った

共通フィールド案:

* `status`: `candidate`, `planned`, `confirmed`, `visited`, `skipped`, `cancelled`, `unplanned`
* `planned_start_at`
* `planned_end_at`
* `actual_start_at`
* `actual_end_at`
* `planned_note`
* `actual_note`
* `source`: `manual`, `google_places`, `imported`, `suggested`
* `confidence`: 推定情報の場合の確信度

予定は「これからどうしたいか」を表す。

実績は「実際に何が起きたか」を表す。

Jarvisは予定と実績の差分を使って、次回旅行への学びを説明できるようにする。

例:

* 予定では水族館に2時間滞在する想定だったが、子どもが喜んで3時間滞在した
* 昼食候補はあったが混雑で行けなかった
* 予定外に公園へ寄った
* 移動時間が想定より長く、次回は休憩を増やすべき

---

## 分類基準

### read / write / mixed

* `read`: 参照、一覧、集計、提案が中心
* `write`: 作成、更新、削除、確定が中心
* `mixed`: 読み取りと更新の両方が自然に必要

### risk level

* `low`: 表示や軽いメモ。家族プライバシーや外部影響が小さい
* `medium`: 家族予定、位置、子ども情報、旅行計画に影響する
* `high`: 予約、支払い、共有、外部サービス連携、家族の詳細な行動履歴に影響する

### confirmation

更新系、削除系、予約や予算に影響する操作、家族に通知される操作は確認を必要とする。

### audit

旅行計画、予約、予算、参加者、子どもの情報、写真連携、外部サービス参照を更新する操作は監査対象にする。

---

## Wishlist

### 目的

Trip作成前の「いつか行きたい場所」や「家族で候補にしたい場所」を管理する。

例:

* 子どもが行きたがっている水族館
* ばあばと行きたい温泉
* 雨の日でも行ける屋内施設

### 主なフィールド案

* `wishlist_id`
* `title`
* `description`
* `place_name`
* `area`
* `provider_place_ref`
* `family_reason`
* `child_friendly_note`
* `priority`
* `season`
* `tags`
* `status`: `candidate`, `shortlisted`, `planned`, `archived`
* `created_by`
* `created_at`
* `updated_at`

### 所属

独立データ。

Tripに採用された場合、SpotまたはTrip候補へ変換する。

### planned / actual

Wishlistは主にplanned以前の候補である。

Tripに採用されたら、Spot側でplanned/actualを持つ。

### 分類

* read/write/mixed: `mixed`
* risk level: `low`から`medium`
* confirmation: Trip採用、削除、共有時に必要
* audit: 採用、削除、優先度変更は必要

### 他Skillとの境界

Wishlistは旅行候補であり、Place検索結果そのものではない。

場所候補の取得はGoogle Places Adapterを利用するが、家族が「行きたい」と判断した理由や優先度はTravelに置く。

### 将来のTool候補

* `travel.list_wishlist_items`
* `travel.create_wishlist_item`
* `travel.update_wishlist_item`
* `travel.convert_wishlist_to_spot`

### 将来のMCP Tool候補

* `travel.wishlist.list`
* `travel.wishlist.create`
* `travel.wishlist.promote_to_trip`

---

## Trip / Outing

### 目的

家族旅行や日帰りのおでかけ全体の単位を管理する。

Tripは、タイトル、日程、都道府県、参加者、Experience、Cover Image、Photo Link、Memoryを束ねる中心である。

宿泊旅行だけでなく、近場のおでかけや「去年何したっけ？」を振り返る単位もTripとして扱う。

### 主なフィールド案

* `trip_id`
* `title`
* `description`
* `destination_area`
* `prefectures`
* `outing_type`: `overnight_trip`, `day_trip`, `short_outing`, `event`
* `planned_start_at`
* `planned_end_at`
* `actual_start_at`
* `actual_end_at`
* `status`: `draft`, `planning`, `confirmed`, `in_progress`, `completed`, `cancelled`
* `participants`
* `family_theme`
* `child_friendly_goal`
* `privacy_level`: `private`, `family`, `shared`
* `share_scope`
* `cover_image_ref`
* `cover_image_status`
* `source`
* `created_by`
* `created_at`
* `updated_at`

### 所属

独立した集約ルート。

他のTravelデータの多くはTripにぶら下がる。

### planned / actual

Trip全体で予定期間と実際のおでかけ期間を分ける。

日帰り予定が宿泊になった、予定より早く帰った、キャンセルになった、などを表現できるようにする。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`
* confirmation: `travel.create_trip` はguarded writeとして確認必須。日程変更、キャンセル、削除も確認必須
* audit: 必要

### 他Skillとの境界

TripはCalendarの予定ではない。

Travelではおでかけ全体の意味、参加者、候補、行程、思い出を束ねる。Calendarには必要に応じて日程表示や通知用の予定を渡す。

### Tool候補

実装済み:

* `travel.create_trip`
* `travel.get_trip`

将来候補:

* `travel.list_trips`
* `travel.update_trip`
* `travel.cancel_trip`
* `travel.summarize_trip`
* `travel.summarize_trip_memories`

### 将来のMCP Tool候補

* `travel.trip.create`
* `travel.trip.get`
* `travel.trip.update`
* `travel.trip.summarize`
* `travel.trip.summarize_memories`

---

## Participants

### 目的

旅行に参加する家族メンバーを管理する。

家族旅行では、参加者ごとに必要な持ち物、移動負担、食事、年齢、注意点が変わる。

例:

* パパ
* ママ
* 子ども
* じいじ
* ばあば

### 主なフィールド案

* `participant_id`
* `trip_id`
* `display_name`
* `role`: `dad`, `mom`, `child`, `grandfather`, `grandmother`, `other`
* `age_group`: `baby`, `toddler`, `child`, `adult`, `senior`
* `needs`
* `allergy_note`
* `mobility_note`
* `packing_responsibility`
* `privacy_level`

### 所属

Tripにぶら下がる。

将来、Family ProfileのようなSkillができた場合は、Travel側にはTrip参加スナップショットを持つ。

### planned / actual

予定参加者と実際の参加者を分ける。

例:

* じいじが予定では参加だったが、実際は不参加
* 子どもが途中で体調不良になり、一部行程だけ参加

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`から`high`
* confirmation: 追加、削除、個人情報更新時に必要
* audit: 必要

### 他Skillとの境界

ParticipantsはFamily Profileそのものではない。

TravelではTrip参加時点のスナップショットを持つ。家族全体のプロフィール、長期的な健康情報、共有権限管理が必要になったら別Skill化を検討する。

### 将来のTool候補

* `travel.add_participant`
* `travel.update_participant`
* `travel.remove_participant`
* `travel.list_participants`

### 将来のMCP Tool候補

* `travel.participants.list`
* `travel.participants.add`
* `travel.participants.update`

---

## Experience

### 目的

旅行やおでかけで家族が体験した、または体験したいことを管理する。

ExperienceはGoogle PlacesのPlaceそのものではない。場所に紐づくことはあるが、Travelの主役は「どこに行ったか」ではなく「家族が何を体験したか」である。

例:

* 朝散歩
* オルカショーでずぶ濡れ
* 新幹線で博多へ
* お家出発！
* お土産は博多駅で見る

### 主なフィールド案

DB / 既存互換では`travel_timeline_items`に保存する。

* `experience_id`
* `timeline_item_id`
* `trip_id`
* `wishlist_id`
* `experience_type`: `spot`, `move`, `event`, `memo`
* `item_type`: 既存互換名。値は`experience_type`と同じ
* `title`
* `display_title`
* `place_name`
* `description`
* `address`
* `location`
* `provider_place_ref`
* `from_label`
* `to_label`
* `from_experience_id`
* `to_experience_id`
* `transport_type`: `car`, `train`, `bus`, `walk`, `taxi`, `flight`, `other`
* `status`: `draft`, `candidate`, `planned`, `confirmed`, `in_progress`, `completed`, `visited`, `skipped`, `cancelled`, `unplanned`, `archived`
* `candidate_group_id`
* `planned_start_at`
* `planned_end_at`
* `actual_start_at`
* `actual_end_at`
* `time_kind`: `planned`, `actual`, `estimated`, `unknown`
* `memo`
* `family_reason`
* `child_friendly_note`
* `restroom_note`
* `stroller_note`
* `rainy_day_note`
* `route_note`
* `rest_stop_note`
* `child_comfort_note`
* `reservation_required`
* `cover_image_ref`
* `cover_image_source`: `google_places_adapter`, `local_cache`, `photo_asset`, `manual`
* `cover_image_status`: `google_placeholder`, `local_cached`, `family_photo_replaced`, `google_placeholder_kept`
* `visibility`: `private`, `family`, `shared`
* `sort_order`
* `archived_at`

`name`または`title`しかない既存データでは、それを`display_title`として扱ってよい。`place_name`と`display_title`を分けられる場合は、`place_name = マリンワールド`、`display_title = オルカショーでずぶ濡れ`のように、場所名と体験タイトルを分離する。

### Experience Type

`spot`は、場所と関係し得る体験である。Google Places参照や住所を持てるが、物理Placeそのものではない。同じ時間帯に複数の`candidate` spot Experienceを並べ、あとで採用、削除、時間変更、別時間帯への移動を行える。

`move`は、移動中の体験である。Spot間や自宅から目的地までの移動予定と実績を表す。新幹線、飛行機、予約済み交通など時間制約のある移動が中心だが、移動中の写真、子どもの反応、車内メモも同じExperienceに紐づけられる。

`event`は、Google Placesにも写真にも紐づかないがTimeline上に置きたい出来事である。出発、到着、休憩、合流、予定変更、家族内の節目などを表す。

`memo`は、Timeline上に置く短い記録や注意である。独立Memo Entityを作るほどではないが、Timelineの文脈で見たい内容を扱う。

### 所属

Tripにぶら下がる。

Experience固有のMemo、Memory、Review、Reservation、Checklist、Photo Linkを追加でぶら下げられる。

### planned / actual

Experienceはplanned/actualとstatusが重要である。

候補、採用、実施済み、行けなかった、予定外、アーカイブを同じモデルで扱えるようにする。

例:

* `candidate`: 10:00 海遊館、10:00 レゴランド、10:00 通天閣のような未確定候補
* `planned`: Timelineに置いたが、まだ相談中
* `confirmed`: 家族で採用した候補
* `in_progress`: 進行中の移動や体験
* `completed` / `visited`: 実際に行った、または完了した
* `skipped`: 候補または予定だったが行かなかった
* `cancelled`: 中止した
* `unplanned`: 当日予定外に立ち寄った、または発生した
* `archived`: 通常表示から外した

### CRUD Tool方針

Canonical Tool:

* `travel.create_experience`
* `travel.get_experience`
* `travel.update_experience`
* `travel.archive_experience`

Alias / UI shortcut:

* `travel.add_spot`
* `travel.add_move`
* `travel.add_memo`

Aliasは本流ではない。UIや会話で短く入力するための入口であり、内部では`experience_type`を指定したCanonical Toolへ寄せる。

既存互換:

* `travel.create_timeline_item`は既存互換として残す
* `travel.get_spot` / `travel.get_spot_photos`が存在する場合は既存互換として残し、将来`travel.get_experience` / `travel.get_experience_photos`へ寄せる

削除は物理削除ではなく`archived`または`archived_at`による論理アーカイブを基本にする。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`
* confirmation: 採用、削除、アーカイブ、訪問実績確定、代表画像変更、共有時に必要
* audit: 必要

### 他Skillとの境界

ExperienceはPlace SkillのPlaceではない。

住所、緯度経度、Google Places参照は持てるが、Google API呼び出しやPlace正規化はGoogle Places Adapterに任せる。

Cover ImageはPhoto Assetではない。訪問前に使う外部Place画像はTravelとGoogle Places Adapter側で扱い、旅行後の家族写真はPhotoに問い合わせる。

Google仮画像を家族写真へ置き換える場合、Travelは採用されたPhoto Asset参照を`cover_image_ref`として保持する。ただしAssetの保存、Thumbnail、Immich連携はPhoto Skillに委譲する。

v0.1ではSpot / Move / Eventを別テーブル化しない。将来、移動経路、予約、詳細なPlace正規化が複雑化した場合だけ派生テーブルを検討する。

### 将来のMCP Tool候補

* `travel.experience.get`
* `travel.experience.create`
* `travel.experience.update`
* `travel.experience.archive`

---

## Reservation

### 目的

旅行に必要な予約情報を管理する。

例:

* ホテル
* 新幹線
* 飛行機
* レストラン
* テーマパークチケット
* レンタカー

### 主なフィールド案

* `reservation_id`
* `trip_id`
* `spot_id`
* `type`: `hotel`, `transport`, `restaurant`, `ticket`, `rental_car`, `other`
* `title`
* `provider_name`
* `reservation_code`
* `reserved_by`
* `participants`
* `planned_start_at`
* `planned_end_at`
* `actual_start_at`
* `actual_end_at`
* `status`: `needed`, `reserved`, `paid`, `used`, `cancelled`, `refunded`
* `price_estimate`
* `actual_price`
* `payment_status`
* `cancel_policy_note`
* `private_note`

### 所属

原則Tripにぶら下がる。

特定Spotに関係する予約はSpotにも紐づける。

### planned / actual

予約予定、予約済み、利用済み、キャンセル、返金を分ける。

実際に利用した時間や金額はactualとして残す。

### 分類

* read/write/mixed: `mixed`
* risk level: `high`
* confirmation: 必要
* audit: 必要

### 他Skillとの境界

ReservationはCalendarではない。

TravelのReservationは、旅行文脈の予約状態、予約番号、支払い状態、キャンセル条件を扱う。Calendarは日程表示や通知を扱う。将来Calendar連携する場合も、予約の正はTravelに置き、Calendarには予定表示として渡す。

### 将来のTool候補

* `travel.add_reservation`
* `travel.update_reservation`
* `travel.list_reservations`
* `travel.check_missing_reservations`
* `travel.mark_reservation_used`

### 将来のMCP Tool候補

* `travel.reservation.list`
* `travel.reservation.add`
* `travel.reservation.update_status`
* `travel.reservation.check_missing`

---

## Cover Image

### 目的

Trip代表画像とSpot代表画像を管理する。

計画時はGoogle Places画像を仮画像として使い、旅行後に実際に撮影した家族写真へ置き換えることがある。置き換えずGoogle仮画像のまま残る場合もある。

Cover ImageはExperience Cardの中心要素である。計画時はGoogle Places由来の仮画像で旅行前のワクワク感を作り、旅行後は家族写真へ置き換えることでMemory画面として機能させられる。置き換えは必須ではなく、Google仮画像のままでもよい。

### 主なフィールド案

* `cover_image_id`
* `owner_type`: `trip`, `spot`
* `owner_id`
* `source`: `google_places_adapter`, `local_cache`, `photo_asset`, `manual`
* `status`: `google_placeholder`, `local_cached`, `family_photo_replaced`, `google_placeholder_kept`
* `provider_place_ref`
* `cached_image_ref`
* `photo_asset_ref`
* `attribution`
* `selected_by`
* `selected_at`
* `updated_at`

### 所属

TripまたはSpotに1つの代表画像参照としてぶら下がる。

履歴や複数候補が必要になった場合は、独立Entityまたは候補テーブルとして扱う。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`
* confirmation: 家族写真への置き換え、共有範囲変更時に必要
* audit: 必要

### 他Skillとの境界

Google Places由来の仮画像取得、ローカル保存、帰属表示、期限管理はTravel + Google Places Adapter側で扱う。

家族写真、Immich Asset、Album、ThumbnailはPhoto Skill側で扱う。TravelはCover Imageとして採用された参照だけを保持し、Photoの保存実装を知らない。

### 将来のTool候補

* `travel.set_trip_cover_image`
* `travel.set_spot_cover_image`
* `travel.replace_cover_image_with_photo`
* `travel.keep_google_cover_image`

### 将来のMCP Tool候補

* `travel.cover_image.get`
* `travel.cover_image.set`
* `travel.cover_image.replace_with_photo`

---

## Photo Link

### 目的

Trip / Outing、Experience、MemoryとPhoto SkillのAsset候補を接続する。

Travelは写真を所有せず、Photo Skillに条件を渡して候補を取得する。明示的に採用された写真参照はTravel側にリンクとして残せる。

### 主なフィールド案

* `photo_link_id`
* `trip_id`
* `owner_type`: `trip`, `experience`, `memory`
* `owner_id`
* `asset_ref`
* `link_type`: `explicit`, `inferred`
* `source`: `time_range`, `location`, `album`, `manual`, `cover_image_replacement`
* `confidence`
* `visibility`: `private`, `family`, `shared`
* `created_by`
* `created_at`

### 所属

Trip配下の関連Entityにぶら下がる。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`から`high`
* confirmation: 明示リンク確定、共有、削除時に必要
* audit: 必要

### 他Skillとの境界

Photo LinkはPhoto AssetをTravelが所有する仕組みではない。写真の正はPhoto Skillにあり、Travelはおでかけ文脈での関連を保持する。

---

## Memory

### 目的

旅行後やおでかけ後に、思い出メモ、写真、子どもの反応、また見たい場面をまとめる。

Reviewは評価や反省に寄りやすい。Travelでは、家族で見返す価値を中心にしたMemoryを主概念にする。

写真、メモ、時刻、体験タイトルが揃っているExperienceは、それ自体がMemoryとして機能する場合がある。別EntityとしてのMemoryは、独立した共有範囲、複数写真、要約、ハイライト選択が必要になったときに使えばよい。

例:

* 娘が水族館で楽しそうだった
* この公園はまた行きたい
* 新幹線で窓の外をずっと見ていた
* 去年の旅行ハイライトに入れたい

### 主なフィールド案

* `memory_id`
* `trip_id`
* `experience_id`
* `participant_id`
* `title`
* `body`
* `memory_type`: `highlight`, `child_reaction`, `good_place`, `again`, `lesson`, `private_note`
* `emotion_tags`
* `photo_query_ref`
* `photo_link_refs`
* `visibility`: `private`, `family`, `shared`
* `created_by`
* `created_at`
* `updated_at`

### 所属

Tripにぶら下がる。

必要に応じてExperience、Participantにも紐づける。

### planned / actual

Memoryは実績側のデータである。

Experienceの時刻、場所、Photo Linkを使い、写真と思い出メモを組み合わせる。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`から`high`
* confirmation: 共有、削除、写真候補との関連確定時に必要
* audit: 必要

### 他Skillとの境界

MemoryはPhoto Albumではない。

Travelでは思い出の文脈、メモ、子どもの反応、再訪意向、ハイライト候補を扱う。写真候補、Thumbnail、Immich連携はPhoto Skillへ問い合わせる。

### 将来のTool候補

* `travel.create_memory`
* `travel.update_memory`
* `travel.summarize_memories`
* `travel.suggest_memories_from_trip`
* `travel.find_related_photos`

### 将来のMCP Tool候補

* `travel.memory.create`
* `travel.memory.summarize`
* `travel.memory.suggest`
* `travel.memory.find_related_photos`

---

## Checklist

### 目的

旅行前、旅行中、旅行後に確認すべきタスクを管理する。

例:

* ホテル予約した？
* チケット取った？
* ベビーカー必要？
* 子どもの保険証を持った？
* 帰宅後に洗濯する？

### 主なフィールド案

* `checklist_item_id`
* `trip_id`
* `spot_id`
* `title`
* `description`
* `category`: `before_trip`, `during_trip`, `after_trip`, `reservation`, `childcare`, `safety`
* `assigned_to`
* `due_at`
* `status`: `todo`, `doing`, `done`, `skipped`
* `priority`
* `confirmation_required`
* `created_by`
* `completed_by`
* `completed_at`

### 所属

原則Tripにぶら下がる。

Spot固有の確認事項はSpotにも紐づける。

### planned / actual

Checklistは予定タスクと実施結果を持つ。

`due_at`がplanned、`completed_at`がactualに相当する。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`
* confirmation: 重要項目の完了、削除、スキップ時に必要
* audit: 重要項目は必要

### 他Skillとの境界

ChecklistはTaskではない。

TravelのChecklistは旅行文脈に閉じた確認事項を扱う。日常の汎用タスク管理が必要になったらTask Skill分離を検討する。初期段階では、旅行準備としてのChecklistはTravelに置く。

### 将来のTool候補

* `travel.add_checklist_item`
* `travel.complete_checklist_item`
* `travel.list_checklist_items`
* `travel.suggest_checklist`

### 将来のMCP Tool候補

* `travel.checklist.list`
* `travel.checklist.add`
* `travel.checklist.complete`
* `travel.checklist.suggest`

---

## Packing

### 目的

旅行に持っていくものを管理する。

家族旅行では、誰の荷物か、誰が準備するか、子ども用か、大人用かが重要である。

例:

* オムツ
* 着替え
* ミルク
* 充電器
* モバイルバッテリー
* 常備薬
* 雨具

### 主なフィールド案

* `packing_item_id`
* `trip_id`
* `participant_id`
* `title`
* `category`: `baby`, `clothes`, `food`, `medicine`, `device`, `document`, `rain`, `other`
* `quantity`
* `assigned_to`
* `status`: `needed`, `prepared`, `packed`, `used`, `missing`, `not_needed`
* `priority`
* `note`
* `prepared_at`
* `packed_at`

### 所属

Tripにぶら下がる。

必要に応じてParticipantに紐づける。

### planned / actual

持っていく予定と実際に使ったもの、足りなかったものを分ける。

次回旅行の提案に使えるよう、`used`, `missing`, `not_needed`を残す。

### 分類

* read/write/mixed: `mixed`
* risk level: `low`から`medium`
* confirmation: 削除、一括完了、重要項目のスキップ時に必要
* audit: 重要項目や子ども関連は必要

### 他Skillとの境界

PackingはInventory全体ではない。

Travelでは今回の旅行に持っていくもの、準備状態、誰の荷物かを扱う。家庭内の在庫管理や購入管理が必要になったらInventoryやShopping系Skill候補に分離する。

### 将来のTool候補

* `travel.add_packing_item`
* `travel.assign_packing_item`
* `travel.mark_packing_prepared`
* `travel.mark_packing_packed`
* `travel.suggest_packing_items`

### 将来のMCP Tool候補

* `travel.packing.list`
* `travel.packing.add`
* `travel.packing.update_status`
* `travel.packing.suggest`

---

## Budget

### 目的

旅行予算と実績金額を管理する。

旅行全体の費用感、カテゴリ別の見込み、実際の支出を家族が把握できるようにする。

### 主なフィールド案

* `budget_item_id`
* `trip_id`
* `spot_id`
* `reservation_id`
* `category`: `transport`, `hotel`, `food`, `ticket`, `souvenir`, `parking`, `other`
* `title`
* `planned_amount`
* `actual_amount`
* `currency`
* `paid_by`
* `payment_method`
* `status`: `estimated`, `planned`, `paid`, `refunded`, `cancelled`
* `private_note`

### 所属

Tripにぶら下がる。

SpotやReservationに関連する支出は紐づける。

### planned / actual

予算はplanned、実際の支払いはactualとして分ける。

予定より高かった、使わなかった、返金された、などを残す。

### 分類

* read/write/mixed: `mixed`
* risk level: `high`
* confirmation: 必要
* audit: 必要

### 他Skillとの境界

BudgetはFinanceではない。

TravelのBudgetは旅行文脈の見込みと実績を扱う。家計簿、銀行連携、カード明細、資産管理はFinance Skill候補である。将来Finance連携する場合も、旅行の費用計画はTravelに置き、支払い明細の正規化はFinanceへ委譲する。

### 将来のTool候補

* `travel.add_budget_item`
* `travel.update_budget_item`
* `travel.summarize_budget`
* `travel.compare_planned_actual_budget`

### 将来のMCP Tool候補

* `travel.budget.list`
* `travel.budget.add`
* `travel.budget.update_actual`
* `travel.budget.summarize`

---

## Memo

### 目的

旅行前、旅行中、旅行後の気づきや注意点を残す。

例:

* この店は子ども椅子があった
* 駐車場が遠かった
* ベビーカーだと階段がきつい
* 次回は朝早く出た方がよい

### 主なフィールド案

* `memo_id`
* `trip_id`
* `experience_id`
* `reservation_id`
* `participant_id`
* `body`
* `category`: `planning`, `during_trip`, `lesson`, `child`, `safety`, `private`
* `visibility`: `private`, `family`, `shared`
* `created_by`
* `created_at`
* `updated_at`

### 所属

Tripにぶら下がる。

必要に応じてExperience、Reservation、Participantにも紐づける。

### planned / actual

Memo自体は予定と実績を直接持たない。

ただし、`planning` Memoは予定側、`during_trip`や`lesson` Memoは実績側として扱える。

### 分類

* read/write/mixed: `mixed`
* risk level: `low`から`high`
* confirmation: private情報、削除、共有時に必要
* audit: private情報や共有変更は必要

### 他Skillとの境界

Memoは汎用Noteではない。

TravelではTrip、Experience、Reservationに紐づく旅行メモを扱う。日常メモ、長期ナレッジ、家族全体のノートが必要になったらNoteやMemory系Skill候補に分離する。

### 将来のTool候補

* `travel.add_memo`
* `travel.list_memos`
* `travel.update_memo`
* `travel.summarize_memos`

### 将来のMCP Tool候補

* `travel.memo.list`
* `travel.memo.add`
* `travel.memo.summarize`

---

## Review

### 目的

旅行後の評価や反省点を管理する補助概念である。

家族のおでかけ記憶では、主概念はMemoryである。Reviewは「良かった点」「大変だった点」「次回改善」など、評価や学びに寄せたい場合に使う。

### 主なフィールド案

* `review_id`
* `trip_id`
* `spot_id`
* `participant_id`
* `rating`
* `child_enjoyment`
* `again_want_to_go`
* `good_points`
* `hard_points`
* `next_time_note`
* `photo_query_ref`
* `created_by`
* `created_at`
* `updated_at`

### 所属

Tripにぶら下がる。

SpotごとのReviewも持てる。

Participantごとの感想を持てるようにする。

### planned / actual

Reviewは実績側のデータである。

planned/actualの差分をもとに、次回への学びを残す。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`
* confirmation: 共有、削除、写真候補との関連確定時に必要
* audit: 必要

### 他Skillとの境界

ReviewはPhoto Albumではない。

Travelでは旅行体験の評価や次回への学びを扱う。写真候補はPhotoに問い合わせるが、Review本文と旅行評価はTravelに置く。

家族で見返す中心データはMemoryであり、ReviewはMemoryから派生して要約されてもよい。

### 将来のTool候補

* `travel.create_review`
* `travel.update_review`
* `travel.summarize_review`
* `travel.suggest_review_from_trip`
* `travel.find_related_photos`

### 将来のMCP Tool候補

* `travel.review.create`
* `travel.review.summarize`
* `travel.review.suggest`
* `travel.review.find_related_photos`

---

## 他Skillとの境界

### Reservation と Calendar

Reservationは旅行文脈の予約情報である。

Calendarは日程表示、通知、空き時間確認を担当する。

予約番号、キャンセル条件、支払い状態、旅行内での必要性はTravelに置く。Calendarへは予定表示として連携する。

### Budget と Finance

Budgetは旅行単位の予算と実績である。

Financeは家計簿、決済明細、口座、カード、資産管理を担当する将来候補である。

Travelでは「この旅行にいくらかかるか」を扱い、Financeでは「家計全体でどう扱うか」を扱う。

### Checklist と Task

Checklistは旅行準備や旅行中確認に閉じた補助タスクである。

Task Skillが将来できた場合、汎用タスク、繰り返しタスク、日常タスクはTaskへ分離する。

初期段階では、現行利用で主役ではないためChecklist実装の優先度は低い。旅行文脈に閉じるChecklistが必要になった場合だけTravelに置く。

### Packing と Inventory

Packingは旅行準備を助ける補助機能である。

現行利用では持ち物チェックは主役ではない。家庭内の在庫管理、購入管理、日常の持ち物管理はInventoryやShopping系Skill候補であり、TravelではTripに閉じた持ち物だけを扱う。

### Spot代表画像 と Photo

Spot代表画像はPhoto Assetではない。

訪問前に表示するGoogle Places画像はTravelとGoogle Places Adapterの責務である。

旅行後の家族写真、Immich Asset、Album、ThumbnailはPhoto Skillの責務である。

Trip代表画像も同じ境界で扱う。TravelはCover Imageとして採用された参照を持つが、Photo Assetの保存やThumbnail生成は持たない。

### Memory と Photo

MemoryはPhoto Albumではない。

Travelは「このTrip / Outingのこの時間、このSpot、このMoveで何が良かったか」という文脈を持つ。Photoはその時間帯や場所に合う写真候補、Thumbnail、Asset権限を返す。

### Sharing / Access Control

Participantsは共有範囲の判断材料になる。

将来じいじばあばに見せる場合、一緒に行ったTrip / Outingだけを見せる必要がある。TravelはTrip、Memory、Memo、Photo Linkごとに`visibility`や`share_scope`を持てるようにする。

本格的な権限管理はFamily/ProfileまたはAccess Control系Skill候補だが、Travelのデータモデルでは以下を前提にする。

* Trip参加者だけが見られるMemoryがある
* 子どもの写真や位置情報は自動共有しない
* 推定Photo Linkは確認前に共有しない
* 共有範囲変更は更新系であり、確認と監査が必要

### Place情報 と Place Skill

現時点ではPlace Skillを作らない。

Spotは旅行文脈の訪問地点である。Google PlacesはAdapterとして扱い、TravelはGoogle APIを直接知らない。

Travel以外の複数SkillがPlace正規化を必要とした時に、Place Skill化を再検討する。

---

## 既存旅行アプリDBとの関係

現在の既存旅行アプリには、概ね以下がある。

* travels
* spots
* moves
* spot代表画像
* travel hero画像
* Immich写真取得

### 既存DBから移行できそうなもの

* `travels` はTripの初期データに移行できる
* `spots` はSpotの初期データに移行できる
* `moves` はMoveの初期データに移行できる
* spot代表画像は、PhotoではなくSpotの`cover_image_ref`として移行できる
* travel hero画像は、Tripの`cover_image_ref`として移行できる

### 既存DBでは足りないもの

* Wishlist
* Participants
* Candidate Spot
* Event / Timeline Item
* Photo Link
* Trip / Spot Cover Imageの状態
* Memory
* Reservation
* Checklist
* Packing
* Budget
* Memo
* Review
* planned/actualの明確な分離
* 家族のおでかけ向けの子ども、休憩、候補相談、再訪意向の情報
* Participantsに基づく共有範囲
* confirmation、audit、privacy levelの設計

### 既存DBから切り離すべきもの

* Immich写真取得はTravelから切り離し、Photo Skillへ委譲する
* Google Places API呼び出し詳細はTravelから切り離し、Google Places Adapterへ委譲する
* 写真Asset、Album、Thumbnailの管理はTravelに持たせない
* 既存DBの都合でTrip、Timeline Item、Photoが密結合している部分はJarvis向けモデルでは分離する

---

## 将来MCP化の見通し

TravelのMCP Toolは、読み取り系から始めるのが安全である。

初期候補:

* `travel.trip.get`
* `travel.trip.list`
* `travel.trip.summarize`
* `travel.experience.get`
* `travel.experience.list`
* `travel.timeline.get`
* `travel.reservation.list`
* `travel.checklist.list`
* `travel.packing.list`
* `travel.budget.summarize`
* `travel.memory.summarize`
* `travel.review.summarize`

更新系候補:

* `travel.trip.create`
* `travel.experience.create`
* `travel.experience.update`
* `travel.experience.archive`
* `travel.reservation.add`
* `travel.checklist.complete`
* `travel.packing.update_status`
* `travel.budget.update_actual`
* `travel.memory.create`
* `travel.review.create`

更新系MCP Toolは、Permission Engine、Confirmation Engine、Audit Logを前提にする。

特にReservation、Budget、Participants、写真連携、外部Place画像は、プライバシー、支払い、外部サービス利用に関係するため慎重に扱う。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。Trip / Outing、Candidate Spot、Timeline、Cover Image、MemoryはWeb UIで相談と振り返りに使いやすい。
2. API / Toolとして利用できるか
   * 利用できる。各データは入力、出力、read/write分類をTool化しやすい粒度に分けている。
3. 将来MCP Tool化できるか
   * できる。読み取り系からMCP化し、更新系は確認と監査を通す方針にできる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。UI専用ではなく、Tripを中心にしたTool境界で設計している。
5. UI依存のロジックになっていないか
   * なっていない。Cover ImageやTimelineは表示に使えるが、モデル自体はTravelの状態と記憶文脈を表す。
6. 読み取り系か更新系か
   * 全体としてはmixed。初期MCP化はread中心、実装が進んだらwriteを追加する。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。参加者、子ども情報、位置情報、写真候補、共有範囲、外部Place画像、予約、予算は確認、権限、監査を前提にする。
