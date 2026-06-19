# Travel Data Model

## 目的

この文書は、Travel Skill実装前に、Jarvis向けのTravelデータモデルを整理するための設計メモである。

既存旅行アプリのDBをそのまま正とせず、家族旅行の計画、実行、振り返りを扱うための理想モデルを先に定義する。

Travelは旅行文脈を持つデータを扱う。写真Asset、Immich、Google Places API、Calendar全体、Finance全体、Task全体はTravelの外に置く。

---

## 全体方針

Travelの主要データ:

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

基本方針:

* Tripを旅行単位の中心にする
* Spot、Move、Reservation、Checklist、Packing、Budget、Memo、Reviewは原則Tripにぶら下げる
* Spotに強く紐づく情報はSpotにもぶら下げられるようにする
* WishlistはTrip作成前の独立データとして扱える
* 旅行文脈に閉じる情報はTravelに置く
* 汎用化が必要になったら、将来Skill分離候補にする

---

## Planned / Actual の考え方

Travelでは、予定と実績を分けて扱う。

同じSpotでも、状態は変化する。

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

## Trip

### 目的

家族旅行全体の単位を管理する。

Tripは、日程、目的地、参加者、Spot、Move、Reservation、Checklist、Packing、Budget、Memo、Reviewを束ねる中心である。

### 主なフィールド案

* `trip_id`
* `title`
* `description`
* `destination_area`
* `planned_start_at`
* `planned_end_at`
* `actual_start_at`
* `actual_end_at`
* `status`: `draft`, `planning`, `confirmed`, `in_progress`, `completed`, `cancelled`
* `participants`
* `family_theme`
* `child_friendly_goal`
* `privacy_level`: `private`, `family`, `shared`
* `cover_image_ref`
* `source`
* `created_by`
* `created_at`
* `updated_at`

### 所属

独立した集約ルート。

他のTravelデータの多くはTripにぶら下がる。

### planned / actual

Trip全体で予定期間と実際の旅行期間を分ける。

日帰り予定が宿泊になった、予定より早く帰った、キャンセルになった、などを表現できるようにする。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`
* confirmation: 作成は不要でもよい。日程変更、キャンセル、削除は必要
* audit: 必要

### 他Skillとの境界

TripはCalendarの予定ではない。

Travelでは旅行全体の意味、参加者、行程、費用、振り返りを束ねる。Calendarには必要に応じて日程表示や通知用の予定を渡す。

### 将来のTool候補

* `travel.create_trip`
* `travel.get_trip`
* `travel.list_trips`
* `travel.update_trip`
* `travel.cancel_trip`
* `travel.summarize_trip`

### 将来のMCP Tool候補

* `travel.trip.create`
* `travel.trip.get`
* `travel.trip.update`
* `travel.trip.summarize`

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

## Spot

### 目的

旅行で訪問する候補地、採用済み地点、実際に訪問した地点を管理する。

SpotはGoogle PlacesのPlaceそのものではなく、家族旅行における訪問地点である。

### 主なフィールド案

* `spot_id`
* `trip_id`
* `wishlist_id`
* `name`
* `description`
* `address`
* `location`
* `provider_place_ref`
* `status`: `candidate`, `planned`, `confirmed`, `visited`, `skipped`, `cancelled`, `unplanned`
* `planned_start_at`
* `planned_end_at`
* `actual_start_at`
* `actual_end_at`
* `family_reason`
* `child_friendly_note`
* `restroom_note`
* `stroller_note`
* `rainy_day_note`
* `reservation_required`
* `cover_image_ref`
* `cover_image_source`: `google_places_adapter`, `manual`
* `sort_order`

### 所属

Tripにぶら下がる。

Spot固有のMemo、Review、Reservation、Checklistを追加でぶら下げられる。

### planned / actual

Spotはplanned/actualが特に重要である。

候補、採用、訪問済み、行けなかった、予定外訪問を同じモデルで扱えるようにする。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`
* confirmation: 採用、削除、訪問実績確定、代表画像変更時に必要
* audit: 必要

### 他Skillとの境界

SpotはPlace SkillのPlaceではない。

Spotは旅行内の訪問地点である。住所、緯度経度、Google Places参照は持てるが、Google API呼び出しやPlace正規化はGoogle Places Adapterに任せる。

Spot代表画像はPhoto Assetではない。訪問前に使う外部Place画像はTravelとGoogle Places Adapter側で扱い、旅行後の家族写真はPhotoに問い合わせる。

### 将来のTool候補

* `travel.add_spot`
* `travel.update_spot`
* `travel.confirm_spot`
* `travel.mark_spot_visited`
* `travel.mark_spot_skipped`
* `travel.search_spot_candidates`
* `travel.set_spot_cover_image`

### 将来のMCP Tool候補

* `travel.spot.list`
* `travel.spot.add`
* `travel.spot.update_status`
* `travel.spot.search_candidates`
* `travel.spot.set_cover_image`

---

## Move

### 目的

Spot間や自宅から目的地までの移動予定と実績を管理する。

家族旅行では、移動時間、休憩、ベビーカー、車内準備、子どもの疲れが重要になる。

### 主なフィールド案

* `move_id`
* `trip_id`
* `from_spot_id`
* `to_spot_id`
* `from_label`
* `to_label`
* `transport_type`: `car`, `train`, `bus`, `walk`, `taxi`, `flight`, `other`
* `planned_start_at`
* `planned_end_at`
* `actual_start_at`
* `actual_end_at`
* `status`: `planned`, `in_progress`, `completed`, `delayed`, `cancelled`
* `route_note`
* `rest_stop_note`
* `child_comfort_note`
* `cost_estimate`
* `actual_cost`

### 所属

Tripにぶら下がる。

必要に応じてSpot間の関係を持つ。

### planned / actual

予定移動時間と実際の移動時間を分ける。

遅延、休憩追加、予定外の寄り道を記録できるようにする。

### 分類

* read/write/mixed: `mixed`
* risk level: `medium`
* confirmation: 重要な行程変更、削除時に必要
* audit: 必要

### 他Skillとの境界

MoveはNavigation全体ではない。

Travelでは旅行計画上の移動区間、予定時間、実績時間、家族向け注意点を扱う。リアルタイム経路探索、渋滞、乗換案内は将来Navigation AdapterまたはNavigation Skill候補に委譲する。

### 将来のTool候補

* `travel.add_move`
* `travel.update_move`
* `travel.mark_move_completed`
* `travel.summarize_moves`

### 将来のMCP Tool候補

* `travel.move.list`
* `travel.move.add`
* `travel.move.update_actual`
* `travel.move.summarize`

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
* `spot_id`
* `move_id`
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

必要に応じてSpot、Move、Reservation、Participantにも紐づける。

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

TravelではTrip、Spot、Move、Reservationに紐づく旅行メモを扱う。日常メモ、長期ナレッジ、家族全体のノートが必要になったらNoteやMemory系Skill候補に分離する。

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

旅行後の振り返りを管理する。

家族旅行では、効率だけではなく、子どもが喜んだか、また行きたいか、次回何を変えるかが重要である。

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

Travelでは旅行体験の振り返り、子どもの反応、再訪意向、次回への学びを扱う。写真候補はPhotoに問い合わせるが、Review本文と旅行評価はTravelに置く。

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

Checklistは旅行準備や旅行中確認に閉じたタスクである。

Task Skillが将来できた場合、汎用タスク、繰り返しタスク、日常タスクはTaskへ分離する。

初期段階では旅行文脈に閉じるChecklistはTravelに置く。

### Spot代表画像 と Photo

Spot代表画像はPhoto Assetではない。

訪問前に表示するGoogle Places画像はTravelとGoogle Places Adapterの責務である。

旅行後の家族写真、Immich Asset、Album、ThumbnailはPhoto Skillの責務である。

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
* Reservation
* Checklist
* Packing
* Budget
* Memo
* Review
* planned/actualの明確な分離
* 家族旅行向けの子ども、荷物、休憩、再訪意向の情報
* confirmation、audit、privacy levelの設計

### 既存DBから切り離すべきもの

* Immich写真取得はTravelから切り離し、Photo Skillへ委譲する
* Google Places API呼び出し詳細はTravelから切り離し、Google Places Adapterへ委譲する
* 写真Asset、Album、Thumbnailの管理はTravelに持たせない
* 既存DBの都合でTrip、Spot、Photoが密結合している部分はJarvis向けモデルでは分離する

---

## 将来MCP化の見通し

TravelのMCP Toolは、読み取り系から始めるのが安全である。

初期候補:

* `travel.trip.get`
* `travel.trip.list`
* `travel.trip.summarize`
* `travel.spot.list`
* `travel.move.list`
* `travel.reservation.list`
* `travel.checklist.list`
* `travel.packing.list`
* `travel.budget.summarize`
* `travel.review.summarize`

更新系候補:

* `travel.trip.create`
* `travel.spot.add`
* `travel.reservation.add`
* `travel.checklist.complete`
* `travel.packing.update_status`
* `travel.budget.update_actual`
* `travel.review.create`

更新系MCP Toolは、Permission Engine、Confirmation Engine、Audit Logを前提にする。

特にReservation、Budget、Participants、写真連携、外部Place画像は、プライバシー、支払い、外部サービス利用に関係するため慎重に扱う。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。Trip、Spot、Checklist、Packing、Budget、ReviewはWeb UIで確認、編集しやすい。
2. API / Toolとして利用できるか
   * 利用できる。各データは入力、出力、read/write分類をTool化しやすい粒度に分けている。
3. 将来MCP Tool化できるか
   * できる。読み取り系からMCP化し、更新系は確認と監査を通す方針にできる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。UI専用ではなく、Tripを中心にしたTool境界で設計している。
5. UI依存のロジックになっていないか
   * なっていない。代表画像や並び順は表示に使えるが、モデル自体はTravelの状態を表す。
6. 読み取り系か更新系か
   * 全体としてはmixed。初期MCP化はread中心、実装が進んだらwriteを追加する。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。予約、予算、参加者、子ども情報、位置情報、写真候補、外部Place画像は確認、権限、監査を前提にする。
