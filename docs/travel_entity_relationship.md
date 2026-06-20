# Travel Entity Relationship

## 目的

この文書は、Travel SkillのEntity Relationshipを整理する設計メモである。

実装前に、Tripを中心としたEntityの親子関係、多重度、予定と実績、他Skillとの境界、既存旅行アプリDBからの移行観点を明確にする。

今回は設計ドキュメントのみを扱う。Runtime、Executor、API、DB、UIは変更しない。

---

## 基本方針

Travelの中心EntityはTripである。

Tripは、家族旅行、日帰りのおでかけ、近場イベントを含む「家族のおでかけ記憶」を束ねる集約ルートとして扱う。

Web UIで失ってはいけないExperience Card原則は[Travel UI Experience Principle](travel_ui_experience.md)に置く。これはWeb UI向けの表示原則であり、MCP Tool / Chat / APIに同じ見た目を強制しない。ただし、Timeline ViewやTool/APIレスポンスはUIが再現に使えるタイトル、時刻、Cover Image、参加者、メモ、写真リンクを返せる必要がある。

```text
Wishlist
  |
  | promote / convert
  v
Trip
├ Participants
├ Candidate Spot
├ Spot
├ Move
├ Event
├ Timeline Item (generated view)
├ Reservation
├ Memo
├ Cover Image
├ Photo Link
├ Memory
├ Checklist
├ Packing
├ Budget
└ Review
```

WishlistはTrip作成前の候補であり、Tripに採用された時点でSpotやTrip候補へ変換される。

Spot、Move、Event、Timeline用MemoはTimelineを構成する要素である。ただしTimelineは原則保存Entityではなく、各Entityから生成されるViewとして扱う。

Spot / Timeline Itemは物理的な場所だけでなく、「朝散歩」「オルカショーでずぶ濡れ」「初めての海」のような体験を表現できる必要がある。既存名称のSpotを今すぐ全て変更する必要はないが、設計上はPlace CardではなくExperience Cardとして表示できる情報を持つ。

```text
Trip
├ Spot
├ Move
├ Event
├ Memo
└ Timeline Item = Spot + Move + Event + Memo から生成されるView
```

旅行文脈に閉じる情報はTravelに置く。汎用化が必要になったら、将来Skill分離候補として扱う。

Packing、Budget、Checklist、Souvenirは補助機能である。現時点の核はTrip / Outing、Candidate Spot、Spot、Move、Event、Memo、Cover Image、Photo Link、Memoryである。

---

## Relationship 全体像

| 親Entity | 子Entity | 多重度 | 必須/任意 | 補足 |
| --- | --- | --- | --- | --- |
| なし | Wishlist | 独立 | 任意 | Trip作成前の候補 |
| なし | Trip / Outing | 独立 | 必須 | Travelの中心。宿泊旅行だけでなく日帰りおでかけも含む |
| Trip | Participants | 1対多 | 任意から開始、実運用では推奨 | 家族旅行では参加者が重要 |
| Trip | Candidate Spot | 1対多 | 任意 | 未確定の訪問候補。同じ時間帯に複数存在できる |
| Trip | Spot | 1対多 | 任意 | 訪問地点、候補、実績 |
| Trip | Move | 1対多 | 任意 | 時間制約のある移動 |
| Trip | Event | 1対多 | 任意 | Placesや写真に紐づかないTimeline上の出来事 |
| Trip | Reservation | 1対多 | 任意 | ホテル、交通、チケットなど |
| Trip | Memo | 1対多 | 任意 | 旅行文脈のメモ |
| Trip | Cover Image | 1対多または参照 | 任意 | Trip代表画像、Spot代表画像 |
| Trip | Photo Link | 1対多 | 任意 | Photo Skill Assetとの明示/推定リンク |
| Trip | Memory | 1対多 | 任意 | 写真と思い出メモを組み合わせた記憶 |
| Trip | Checklist | 1対多 | 任意 | 補助機能。旅行準備、旅行中、旅行後の確認 |
| Trip | Packing | 1対多 | 任意 | 補助機能。持ち物 |
| Trip | Budget | 1対多 | 任意 | 補助機能。予算、支出実績 |
| Trip | Review | 1対多 | 任意 | 補助機能。評価や反省 |
| Spot | Reservation | 1対多 | 任意 | Spotに紐づく予約 |
| Spot | Checklist | 1対多 | 任意 | Spot固有の確認事項 |
| Spot | Budget | 1対多 | 任意 | Spotに紐づく支出 |
| Spot | Memo | 1対多 | 任意 | Spotメモ |
| Spot | Memory | 1対多 | 任意 | Spot別の思い出 |
| Spot | Review | 1対多 | 任意 | Spot別振り返り |
| Move | Memo | 1対多 | 任意 | 移動中の気づき |
| Move | Memory | 1対多 | 任意 | 移動中の思い出 |
| Event | Memo | 1対多 | 任意 | Event補足 |
| Event | Memory | 1対多 | 任意 | Eventに紐づく思い出 |
| Reservation | Budget | 1対多 | 任意 | 予約に紐づく費用 |
| Reservation | Memo | 1対多 | 任意 | 予約メモ |
| Participants | Packing | 1対多 | 任意 | 参加者別荷物 |
| Participants | Memory | 1対多 | 任意 | 参加者別の思い出 |
| Participants | Review | 1対多 | 任意 | 参加者別感想 |
| Participants | Memo | 1対多 | 任意 | 参加者に関する注意 |

---

## Planned / Actual

Travelでは予定と実績を分けて扱う。

予定は「旅行前にどうしたいか」を表し、実績は「実際に何が起きたか」を表す。

| Entity | planned | actual | status例 |
| --- | --- | --- | --- |
| Trip | planned_start_at, planned_end_at | actual_start_at, actual_end_at | draft, planning, confirmed, in_progress, completed, cancelled |
| Participants | planned参加者 | actual参加者、一部参加 | planned, joined, absent, partial |
| Spot / Candidate Spot | planned_start_at, planned_end_at | actual_start_at, actual_end_at | candidate, planned, confirmed, visited, skipped, cancelled, unplanned |
| Move | planned_start_at, planned_end_at | actual_start_at, actual_end_at | planned, in_progress, completed, delayed, cancelled |
| Event | planned_at | actual_at | planned, happened, skipped |
| Reservation | 予約予定、利用予定 | 利用済み、キャンセル、返金 | needed, booked, paid, used, canceled, refunded |
| Checklist | due_at | completed_at | todo, doing, done, skipped |
| Packing | needed, prepared予定 | packed, used, missing, not_needed | needed, prepared, packed, used, missing, not_needed |
| Budget | planned_amount | actual_amount | estimated, planned, paid, refunded, cancelled |
| Memo | planning memo | during_trip, lesson memo | planning, during_trip, lesson |
| Memory | なし | 思い出メモ、写真リンク、子どもの反応 | draft, completed, shared |
| Review | なし | 評価、反省、次回改善 | draft, completed, shared |

planned/actualを分けることで、Jarvisは旅行後に「予定との差分」と「次回への学び」を説明できる。

---

## 多重度の扱い

初期モデルでは、Tripを親にした1対多を基本にする。

| 種類 | Travelでの扱い | 例 |
| --- | --- | --- |
| 1対1 | 必要な場合だけ派生情報として扱う | TripとTrip代表画像参照、SpotとSpot代表画像参照 |
| 1対多 | 基本形 | TripとSpot、TripとMove、TripとReservation |
| 多対多 | 初期は明示的な中間Entityまたは参照配列で扱い、必要になったら中間テーブル化する | ParticipantsとReservation、ParticipantsとChecklist、SpotとParticipants |

多対多を最初から広く正規化しすぎると、初期実装の負荷が大きくなる。まずはTrip配下のEntityを安定させ、実運用で必要になった関係から中間テーブルを追加する。

将来の中間テーブル候補:

* `travel_reservation_participants`
* `travel_checklist_assignees`
* `travel_spot_participants`
* `travel_photo_links`

`travel_photo_links`はPhoto AssetをTravelが所有するためのテーブルではない。MemoryやCover Image置き換えで使う写真候補や明示リンクを記録する場合の接続テーブル候補であり、写真の正はPhoto Skillに置く。

---

## Entity 別設計

### Wishlist

| 項目 | 内容 |
| --- | --- |
| 親Entity | なし |
| 子Entity | なし。Trip採用後はSpotへ変換される |
| 多重度 | 独立Entity。1つのWishlist Itemは0または1つのTrip/Spotへ採用される |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | Trip作成前の「いつか行きたい」を保持するため |
| Tripに内包しない理由 | Tripが未作成でも候補を保存したい。複数Tripの候補にもなり得る |
| Spotに内包しない理由 | SpotはTrip内の訪問地点であり、WishlistはTrip採用前の候補であるため |
| 将来DBテーブル候補 | `travel_wishlist_items` |
| 将来API候補 | `GET /travel/wishlist`, `POST /travel/wishlist`, `POST /travel/wishlist/{id}/promote` |
| 将来Tool候補 | `travel.list_wishlist_items`, `travel.create_wishlist_item`, `travel.update_wishlist_item`, `travel.convert_wishlist_to_spot` |

WishlistはPlace検索結果そのものではない。Google Places Adapterから得た候補を参考にしつつ、家族が行きたい理由、季節、優先度をTravel側に保持する。

### Trip / Outing

| 項目 | 内容 |
| --- | --- |
| 親Entity | なし |
| 子Entity | Participants, Candidate Spot, Spot, Move, Event, Reservation, Memo, Cover Image, Photo Link, Memory, Checklist, Packing, Budget, Review |
| 多重度 | 1つのTripに各子Entityが0..N |
| 必須/任意 | 必須。Travelの中心 |
| 独立Entityにする理由 | 旅行またはおでかけ単位の集約ルートであり、タイトル、日程、都道府県、参加者、候補、行程、思い出を束ねるため |
| Tripに内包しない理由 | 該当なし |
| Spotに内包しない理由 | SpotはTripの一部であり、Trip全体の期間、参加者、候補群、Memory、共有範囲を表せないため |
| 将来DBテーブル候補 | `travel_trips` |
| 将来API候補 | `GET /travel/trips`, `POST /travel/trips`, `GET /travel/trips/{trip_id}`, `PATCH /travel/trips/{trip_id}` |
| 実装済みTool | `travel.create_trip`, `travel.get_trip` |
| 将来Tool候補 | `travel.list_trips`, `travel.update_trip`, `travel.cancel_trip`, `travel.summarize_trip`, `travel.summarize_trip_memories` |

TripはCalendar Eventではない。Calendarは日程表示や通知を担当し、Travelはおでかけの意味、状態、参加者、候補、行程、思い出を担当する。

### Participants

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip |
| 子Entity | Packing, Memo, Memory, Review |
| 多重度 | Trip 1対多 Participants。Participant 1対多 Packing/Memo/Memory/Review |
| 必須/任意 | 任意。ただし家族旅行では実運用上ほぼ必須 |
| 独立Entityにする理由 | 参加者ごとに荷物、注意点、移動負担、感想が異なるため |
| Tripに内包しない理由 | 配列として埋め込むとPacking、Memory、Reviewから参照しにくく、参加者別状態を持てないため |
| Spotに内包しない理由 | 参加者はTrip全体に関係し、特定Spotだけの属性ではないため |
| 将来DBテーブル候補 | `travel_participants` |
| 将来API候補 | `GET /travel/trips/{trip_id}/participants`, `POST /travel/trips/{trip_id}/participants`, `PATCH /travel/participants/{participant_id}` |
| 将来Tool候補 | `travel.list_participants`, `travel.add_participant`, `travel.update_participant`, `travel.remove_participant` |

ParticipantsはFamily/Profileそのものではない。TravelではTrip参加時点のスナップショットを持つ。家族全体のプロフィール、長期的な健康情報、共有権限管理は将来Family/Profile Skill候補である。

### Spot

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip |
| 子Entity | Reservation, Checklist, Budget, Memo, Memory, Review |
| 多重度 | Trip 1対多 Spot。Spot 1対多 子Entity |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | 未確定候補、訪問予定、訪問実績、Google Places参照、代表画像、家族向け注意点を持つため |
| Tripに内包しない理由 | 同じ時間帯の複数候補、Reservation、Checklist、Budget、Memo、Memory、Reviewから参照され、Timeline生成にも使うため |
| Spotに内包しない理由 | 該当なし |
| 将来DBテーブル候補 | `travel_spots` |
| 将来API候補 | `GET /travel/trips/{trip_id}/spots`, `POST /travel/trips/{trip_id}/spots`, `PATCH /travel/spots/{spot_id}` |
| 将来Tool候補 | `travel.add_spot`, `travel.update_spot`, `travel.confirm_spot`, `travel.move_spot_time`, `travel.mark_spot_visited`, `travel.mark_spot_skipped`, `travel.search_spot_candidates`, `travel.set_spot_cover_image` |

SpotはPlace SkillのPlaceではない。Spotは「このTripで訪問する地点」であり、Google PlacesはAdapterとして参照する。

Spotは物理的な場所だけでなく、Trip内の体験を表現できる。たとえば`place_name = マリンワールド`、`display_title = オルカショーでずぶ濡れ`のように、場所名とUI向け体験タイトルが異なる場合を許容する。

Spotの`candidate`状態は計画中の主役である。例として、10:00に海遊館、レゴランド、通天閣が並び、あとで1つを採用する、削除する、時間をずらす、当日まで候補のまま残す、という使い方を許容する。

Spot代表画像はPhoto Assetではない。訪問前に使うGoogle Places画像はTravelとGoogle Places Adapter側で扱い、旅行後の家族写真はPhoto Skillへ問い合わせる。

### Move

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip |
| 子Entity | Memo |
| 多重度 | Trip 1対多 Move。Moveはfrom_spot/to_spotへ0..1ずつ参照できる |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | 移動時間、交通手段、遅延、休憩、子どもの負担をSpotとは別に記録するため |
| Tripに内包しない理由 | Timeline生成、予定/実績比較、Spot間参照に使うため |
| Spotに内包しない理由 | Moveは2つの地点またはラベル間の関係であり、片方のSpotに閉じないため |
| 将来DBテーブル候補 | `travel_moves` |
| 将来API候補 | `GET /travel/trips/{trip_id}/moves`, `POST /travel/trips/{trip_id}/moves`, `PATCH /travel/moves/{move_id}` |
| 将来Tool候補 | `travel.add_move`, `travel.update_move`, `travel.mark_move_completed`, `travel.summarize_moves` |

MoveはNavigation全体ではない。Travelでは旅行行程上の移動区間と実績を扱い、リアルタイム経路探索や乗換案内は将来Navigation AdapterまたはNavigation Skill候補に委譲する。

Moveは主に時間制約がある移動を書く。新幹線、飛行機、予約済み交通などが中心で、座席番号などはReservationまたはMoveのMemoに残す。

### Event

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip |
| 子Entity | Memo, Memory |
| 多重度 | Trip 1対多 Event。Event 1対多 Memo/Memory |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | Google Placesや写真がなくてもTimeline上に置きたい出来事を扱うため |
| Tripに内包しない理由 | Timeline生成、Memory、Memoから参照され、planned/actualや共有範囲を持つため |
| Spotに内包しない理由 | Eventは場所に閉じない出来事も多いため |
| 将来DBテーブル候補 | `travel_events` |
| 将来API候補 | `GET /travel/trips/{trip_id}/events`, `POST /travel/trips/{trip_id}/events`, `PATCH /travel/events/{event_id}` |
| 将来Tool候補 | `travel.add_event`, `travel.update_event`, `travel.list_events` |

EventはCalendar Eventではない。Travel上の「お家出発！」「ホテル到着」「じいじばあばと合流」のような記憶やTimeline表示のための出来事である。

### Reservation

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip。任意でSpot |
| 子Entity | Budget, Memo |
| 多重度 | Trip 1対多 Reservation。Spot 1対多 Reservation。Reservation 1対多 Budget/Memo |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | 予約番号、予約状態、支払い、キャンセル条件、利用実績を安全に扱うため |
| Tripに内包しない理由 | 予約ごとに状態、期限、金額、関連Spot、関連Budgetがあり、更新リスクが高いため |
| Spotに内包しない理由 | ホテルや交通予約のように特定Spotへ閉じない予約があるため |
| 将来DBテーブル候補 | `travel_reservations` |
| 将来API候補 | `GET /travel/trips/{trip_id}/reservations`, `POST /travel/trips/{trip_id}/reservations`, `PATCH /travel/reservations/{reservation_id}` |
| 将来Tool候補 | `travel.list_reservations`, `travel.add_reservation`, `travel.update_reservation`, `travel.check_missing_reservations`, `travel.mark_reservation_used` |

ReservationはCalendarではない。Travelは予約の正を持ち、Calendarには日程表示や通知用の予定として連携する。外部予約サービスへの変更は副作用が大きいため、初期はTravel内メモと状態管理に留める。

### Checklist

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip。任意でSpot |
| 子Entity | なし |
| 多重度 | Trip 1対多 Checklist。Spot 1対多 Checklist |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | due、担当者、完了者、完了時刻、重要度を持つ旅行タスクとして扱うため |
| Tripに内包しない理由 | 個別完了、担当変更、提案、監査を行う粒度として独立しているため |
| Spotに内包しない理由 | Trip全体の準備や帰宅後タスクもあるため |
| 将来DBテーブル候補 | `travel_checklist_items` |
| 将来API候補 | `GET /travel/trips/{trip_id}/checklist`, `POST /travel/trips/{trip_id}/checklist`, `PATCH /travel/checklist/{item_id}` |
| 将来Tool候補 | `travel.list_checklist_items`, `travel.add_checklist_item`, `travel.complete_checklist_item`, `travel.suggest_checklist` |

ChecklistはTaskではない。旅行文脈に閉じた確認事項はTravelに置く。日常タスク、繰り返しタスク、家族横断のタスク管理が必要になったらTask Skill分離候補にする。

### Packing

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip。任意でParticipants |
| 子Entity | なし |
| 多重度 | Trip 1対多 Packing。Participant 1対多 Packing |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | 誰の荷物か、誰が準備するか、数量、準備状態、実際に使ったかを持つため |
| Tripに内包しない理由 | 参加者別、カテゴリ別、準備状態別に更新し、次回提案に使うため |
| Spotに内包しない理由 | 持ち物は旅行全体と参加者に関係し、特定Spotに閉じないことが多いため |
| 将来DBテーブル候補 | `travel_packing_items` |
| 将来API候補 | `GET /travel/trips/{trip_id}/packing`, `POST /travel/trips/{trip_id}/packing`, `PATCH /travel/packing/{item_id}` |
| 将来Tool候補 | `travel.add_packing_item`, `travel.assign_packing_item`, `travel.mark_packing_prepared`, `travel.mark_packing_packed`, `travel.suggest_packing_items` |

PackingはInventory全体ではない。家庭内の在庫、購入管理、消耗品管理が必要になったらInventoryやShopping系Skill候補に分離する。

### Budget

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip。任意でSpot、Reservation |
| 子Entity | なし |
| 多重度 | Trip 1対多 Budget。Spot 1対多 Budget。Reservation 1対多 Budget |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | 予算、実績、支払い状態、返金、カテゴリ集計を扱うため |
| Tripに内包しない理由 | 明細単位で更新、集計、planned/actual比較、監査が必要なため |
| Spotに内包しない理由 | 交通費、宿泊費、旅行全体費用などSpotに閉じない費用があるため |
| 将来DBテーブル候補 | `travel_budget_items` |
| 将来API候補 | `GET /travel/trips/{trip_id}/budget`, `POST /travel/trips/{trip_id}/budget`, `PATCH /travel/budget/{budget_item_id}` |
| 将来Tool候補 | `travel.add_budget_item`, `travel.update_budget_item`, `travel.summarize_budget`, `travel.compare_planned_actual_budget` |

BudgetはFinanceではない。Travelは「この旅行にいくらかかるか」を扱う。カード明細、口座、家計簿、資産管理はFinance Skill候補である。

### Memo

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip。任意でSpot、Move、Event、Reservation、Participants |
| 子Entity | なし |
| 多重度 | Trip 1対多 Memo。各関連Entity 1対多 Memo |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | 旅行前、旅行中、旅行後の気づきやTimeline上の短いメモを対象Entityへ柔軟に紐づけるため |
| Tripに内包しない理由 | Spot、Move、Event、Reservation、Participant単位で参照したいメモがあるため |
| Spotに内包しない理由 | 移動、Event、予約、参加者、旅行全体に関するメモもあるため |
| 将来DBテーブル候補 | `travel_memos` |
| 将来API候補 | `GET /travel/trips/{trip_id}/memos`, `POST /travel/trips/{trip_id}/memos`, `PATCH /travel/memos/{memo_id}` |
| 将来Tool候補 | `travel.add_memo`, `travel.list_memos`, `travel.update_memo`, `travel.summarize_memos` |

Memoは汎用Noteではない。旅行文脈に閉じたメモはTravelに置き、日常メモ、長期ナレッジ、家族全体のノートはNoteやMemory系Skill候補にする。

### Cover Image

| 項目 | 内容 |
| --- | --- |
| 親Entity | TripまたはSpot |
| 子Entity | なし |
| 多重度 | Trip 0..1代表画像、Spot 0..1代表画像。候補履歴を持つ場合は1対多 |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | Google仮画像、ローカル保存画像、家族写真置き換えを同じ参照として扱うため |
| Tripに内包しない理由 | Trip代表画像とSpot代表画像で共通の状態、source、attribution、Photo参照を持つため |
| Spotに内包しない理由 | Trip代表画像にも使うため |
| 将来DBテーブル候補 | `travel_cover_images` または `travel_trips.cover_image_ref` / `travel_spots.cover_image_ref` |
| 将来API候補 | `PATCH /travel/trips/{trip_id}/cover-image`, `PATCH /travel/spots/{spot_id}/cover-image` |
| 将来Tool候補 | `travel.set_trip_cover_image`, `travel.set_spot_cover_image`, `travel.replace_cover_image_with_photo` |

Google Places由来の仮画像はTravel + Google Places Adapter側で扱う。家族が撮影した写真はPhoto Skill側で扱い、TravelはCover Imageとして採用された参照だけを持つ。

Cover Imageの状態例:

* `google_placeholder`
* `local_cached`
* `family_photo_replaced`
* `google_placeholder_kept`

### Photo Link

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip。任意でSpot、Move、Event、Memory |
| 子Entity | なし |
| 多重度 | 各Travel Entity 1対多 Photo Link |
| 必須/任意 | 任意 |
| 独立Entityにする理由 | 明示リンクと推定リンク、source、confidence、visibilityを区別するため |
| Tripに内包しない理由 | Spot、Move、Event、Memory単位で写真候補を扱うため |
| Spotに内包しない理由 | Trip全体、Move、Event、Memoryにも写真リンクが必要なため |
| 将来DBテーブル候補 | `travel_photo_links` |
| 将来API候補 | `GET /travel/trips/{trip_id}/photo-links`, `POST /travel/photo-links`, `PATCH /travel/photo-links/{photo_link_id}` |
| 将来Tool候補 | `travel.find_related_photos`, `travel.link_photo_to_memory`, `travel.link_photo_to_spot` |

Photo LinkはPhoto AssetをTravelが所有するためのEntityではない。写真の正はPhoto Skillにあり、TravelはTrip / Outing文脈での関連を保持する。

### Memory

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip。任意でSpot、Move、Event、Participants |
| 子Entity | Photo Link |
| 多重度 | Trip 1対多 Memory。Memory 1対多 Photo Link |
| 必須/任意 | 任意。旅行後または旅行中に作成される |
| 独立Entityにする理由 | 思い出メモ、写真、子どもの反応、もう一度見たい場面をまとめるため |
| Tripに内包しない理由 | Spot、Move、Event、Participant別に参照され、共有範囲や写真リンクを持つため |
| Spotに内包しない理由 | 移動中の思い出、Trip全体のハイライト、Eventの記憶もあるため |
| 将来DBテーブル候補 | `travel_memories` |
| 将来API候補 | `GET /travel/trips/{trip_id}/memories`, `POST /travel/trips/{trip_id}/memories`, `PATCH /travel/memories/{memory_id}` |
| 将来Tool候補 | `travel.create_memory`, `travel.summarize_memories`, `travel.suggest_memories_from_trip` |

MemoryはReviewより主役である。Reviewが評価や反省に寄るのに対し、Memoryは「家族で見返したい記憶」を扱う。

ただし、別EntityとしてのMemoryを急いで作る必要はない。写真、メモ、時刻、体験タイトルを持つSpot / Timeline Itemが、そのままMemoryとして機能する場合がある。

### Review

| 項目 | 内容 |
| --- | --- |
| 親Entity | Trip。任意でSpot、Participants |
| 子Entity | なし |
| 多重度 | Trip 1対多 Review。Spot 1対多 Review。Participant 1対多 Review |
| 必須/任意 | 任意。旅行後に必要な場合だけ作成される |
| 独立Entityにする理由 | 旅行体験の評価、再訪意向、次回改善点を実績として残すため |
| Tripに内包しない理由 | Spot別、参加者別、写真候補連携、共有範囲を持てるようにするため |
| Spotに内包しない理由 | Trip全体の振り返りや参加者別感想もあるため |
| 将来DBテーブル候補 | `travel_reviews` |
| 将来API候補 | `GET /travel/trips/{trip_id}/reviews`, `POST /travel/trips/{trip_id}/reviews`, `PATCH /travel/reviews/{review_id}` |
| 将来Tool候補 | `travel.create_review`, `travel.update_review`, `travel.summarize_review`, `travel.suggest_review_from_trip`, `travel.find_related_photos` |

ReviewはPhoto Albumではない。旅行後の家族写真候補はPhoto Skillへ問い合わせるが、旅行評価、感想、次回への学びはTravelに置く。家族で見返す中心はMemoryであり、Reviewは補助的な評価データとして扱う。

---

## Timeline Item

TimelineはSpot、Move、Event、Timeline用Memoから構成する。

保存するのは各Entityであり、Timeline Itemは原則保存Entityではなく生成Viewである。

```text
Event: お家出発！
Move: 自宅 -> 新幹線
Spot: 海遊館
Memo: お土産は博多駅で見る
Event: ホテル到着
```

Timeline Itemの種類:

* `place_spot`
* `experience`
* `move`
* `event`
* `memo`

Timeline生成時は、Spotの`planned_start_at`/`actual_start_at`、Moveの`planned_start_at`/`actual_start_at`、Eventの`planned_at`/`actual_at`、Memoの表示時刻、`sort_order`を使う。

Web UI向けのTimeline Viewでは、Experience Cardを再現できるように`title`、`display_title`、`place_name`、`start_time`、`end_time`、`cover_image`、`item_type`、`participants`、`memo`、`linked_photos`を含められるようにする。MCP Tool / Chat / APIは時計アイコンや中央配置文字を返す必要はない。

planned Timelineは旅行前の予定表示に使う。actual Timelineは旅行中または旅行後の実績表示に使う。

Timelineを保存Entityにしない理由:

* Spot、Move、Event、Memoの重複データになる
* planned/actual差分が二重管理になる
* 並び替えや遅延時に整合性が崩れやすい
* API/Toolでは`travel.timeline.get`のような読み取りViewとして提供すれば足りる

ただし、Timeline表示専用のメタデータや明示的な並び固定が必要になった場合は、`travel_timeline_items`を将来候補として再検討する。

将来Tool候補:

* `travel.get_timeline`
* `travel.get_planned_timeline`
* `travel.get_actual_timeline`
* `travel.compare_planned_actual_timeline`

---

## 他Skillとの境界

### Reservation と Calendar

Travelに置く理由:

* 予約番号、予約状態、支払い、キャンセル条件は旅行文脈に強く結びつく
* ホテル、交通、チケット、レストラン予約はTripの成立条件である

将来分離候補:

* Calendarは日程表示、通知、空き時間確認を担当する
* Calendar連携する場合も、予約の正はTravel、表示イベントはCalendarに置く

### Checklist と Task

Travelに置く理由:

* 「旅行前に必要」「旅行中に確認」「帰宅後にやる」という文脈が重要である
* 子ども連れ、荷物、予約確認などTravel固有の提案に使う

将来分離候補:

* 汎用タスク、繰り返しタスク、家族横断のTodo管理が必要になったらTask Skill候補にする

### Budget と Finance

Travelに置く理由:

* 旅行単位の予算、見込み、実績、カテゴリ集計が必要である
* planned/actual比較がTrip MemoryやReviewに使える

将来分離候補:

* 家計簿、カード明細、銀行連携、資産管理はFinance Skill候補にする
* Finance連携時も、旅行計画上の予算はTravelに置く

### Spot画像 と Photo

Travelに置く理由:

* Spot代表画像は訪問前にも必要である
* Google Places画像は家族写真Assetではない
* Spot表示のための代表画像選択はTravelの文脈に近い

将来分離候補:

* 旅行後の家族写真、Immich Asset、Album、ThumbnailはPhoto Skillが担当する
* Travelは`trip_id`、`spot_id`、期間、位置情報を渡してPhotoへ問い合わせる

### Place情報 と Place Skill

Travelに置く理由:

* 現時点ではPlace Skillを作らない方針である
* Spotは旅行文脈の訪問地点であり、汎用Placeではない
* Google PlacesはAdapterとして扱う

将来分離候補:

* Calendar、Navigation、Weather、Home、Photoなど複数Skillが共通Place正規化を必要とした場合にPlace Skill化を再検討する

### Participants と Family/Profile

Travelに置く理由:

* Trip参加時点のスナップショットが必要である
* 参加者によって休憩、食事、移動負担、Memory、Reviewが変わる

将来分離候補:

* 家族全体のプロフィール、長期的な健康情報、権限、共有範囲はFamily/Profile Skill候補にする
* Travel側にはTrip参加時点の参照またはスナップショットを残す

---

## 既存旅行アプリDBとの比較

既存旅行アプリには概ね以下がある。

* travels
* spots
* moves
* spot代表画像
* travel hero画像
* Immich写真取得

### 既存DBからそのまま使えそうな関係

| 既存DB | 新モデル | 補足 |
| --- | --- | --- |
| travels | Trip | 旅行単位として利用できる |
| spots | Spot | Trip配下の訪問地点として利用できる |
| moves | Move | Trip配下の移動区間として利用できる |
| spot代表画像 | Spot.cover_image_ref | PhotoではなくTravel + Google Places Adapter側で扱う |
| travel hero画像 | Trip.cover_image_ref | Trip表示用の代表画像として扱う |

### 既存DBでは足りない関係

* Wishlist
* Participants
* Reservation
* Event
* Timeline Item生成に必要なEvent/Memo表示情報
* Cover Imageのsource/status
* Photo Link
* Memory
* Candidate Spotのgroup/status
* Checklist
* Packing
* Budget
* Memo
* Review
* planned/actualの明確な分離
* ReservationとBudgetの関係
* SpotとChecklist/Memo/Reviewの関係
* ParticipantとPacking/Reviewの関係
* privacy level、confirmation、auditの設計
* Participantsに基づくAccess Control
* 子ども連れ、休憩、候補相談、再訪意向など家族のおでかけ記憶文脈

### 既存DBから切り離すべき関係

* Immich写真取得はTravelから切り離し、Photo Skillへ委譲する
* Photo Asset、Album、ThumbnailはTravel DBの正にしない
* Google Places API呼び出し詳細はGoogle Places Adapterへ切り離す
* Google Placesの外部IDや画像キャッシュの詳細をSpotモデルへ漏らしすぎない
* Timelineを保存テーブルとして固定せず、Spot + Move + Event + Memoから生成する

### 新モデルに移行するなら最初に扱うべき最小関係

最初は既存DBの強みを活かし、次の最小関係から扱う。

```text
Trip
├ Spot
├ Move
└ Event

Timeline = Spot + Move + Event + Memo
```

最小実装に進むなら、優先順は以下がよい。

1. `Trip 1対多 Spot`
2. `Trip 1対多 Move`
3. `Trip 1対多 Event`
4. `Spot/Move/Event planned_actual`
5. `Spot status`: `candidate`, `planned`, `visited`, `skipped`
6. `Trip Timeline View`
7. `Trip/Spot cover_image_ref`とsource/status
8. `Trip 1対多 Memo`
9. `Trip 1対多 Memory`
10. `Travel -> Photo`の読み取り系Photo Link候補
11. `Trip 1対多 Participants`
12. `Participants`に基づく共有範囲
13. `Trip 1対多 Reservation`
14. `Trip 1対多 Checklist`
15. `Trip 1対多 Packing`
16. `Trip 1対多 Budget`
17. `Trip 1対多 Review`

初期は読み取り系から始める。更新系はPermission、Confirmation、Auditの方針が固まってから追加する。

既存DBは今すぐ変更しない。今回の補正は設計文書だけであり、Runtime、Executor、API、DB、UIには影響させない。最小実装へ進む場合も、既存の`travels`、`spots`、`moves`を読み取り中心に解釈し、Event、Memory、Photo Link、Access Controlは段階的に追加する。

---

## 将来DBテーブル候補まとめ

* `travel_wishlist_items`
* `travel_trips`
* `travel_participants`
* `travel_spots`
* `travel_moves`
* `travel_events`
* `travel_cover_images`
* `travel_photo_links`
* `travel_memories`
* `travel_reservations`
* `travel_checklist_items`
* `travel_packing_items`
* `travel_budget_items`
* `travel_memos`
* `travel_reviews`

Timelineは原則テーブル候補にしない。`travel_spots`、`travel_moves`、`travel_events`、`travel_memos`から生成するViewまたはAPIレスポンスとして扱う。

---

## 将来API候補まとめ

読み取り系:

* `GET /travel/wishlist`
* `GET /travel/trips`
* `GET /travel/trips/{trip_id}`
* `GET /travel/trips/{trip_id}/participants`
* `GET /travel/trips/{trip_id}/spots`
* `GET /travel/trips/{trip_id}/moves`
* `GET /travel/trips/{trip_id}/events`
* `GET /travel/trips/{trip_id}/timeline`
* `GET /travel/trips/{trip_id}/memories`
* `GET /travel/trips/{trip_id}/photo-links`
* `GET /travel/trips/{trip_id}/reservations`
* `GET /travel/trips/{trip_id}/checklist`
* `GET /travel/trips/{trip_id}/packing`
* `GET /travel/trips/{trip_id}/budget`
* `GET /travel/trips/{trip_id}/memos`
* `GET /travel/trips/{trip_id}/reviews`

更新系:

* `POST /travel/wishlist`
* `POST /travel/wishlist/{id}/promote`
* `POST /travel/trips`
* `PATCH /travel/trips/{trip_id}`
* `POST /travel/trips/{trip_id}/participants`
* `POST /travel/trips/{trip_id}/spots`
* `POST /travel/trips/{trip_id}/moves`
* `POST /travel/trips/{trip_id}/events`
* `POST /travel/trips/{trip_id}/memories`
* `POST /travel/trips/{trip_id}/reservations`
* `POST /travel/trips/{trip_id}/checklist`
* `POST /travel/trips/{trip_id}/packing`
* `POST /travel/trips/{trip_id}/budget`
* `POST /travel/trips/{trip_id}/memos`
* `POST /travel/trips/{trip_id}/reviews`

更新系APIは、家族の予定、位置、予約、支払い、写真候補、個人情報に影響するため、確認、権限、監査を前提にする。

---

## 将来Tool候補まとめ

実装済みTravel Tool:

* `travel.get_trips`
* `travel.get_trip`
* `travel.get_trip_timeline`
* `travel.create_trip`
* `travel.create_timeline_item`

読み取り系:

* `travel.list_wishlist_items`
* `travel.list_trips`
* `travel.summarize_trip`
* `travel.list_participants`
* `travel.list_spots`
* `travel.list_moves`
* `travel.list_events`
* `travel.get_timeline`
* `travel.list_memories`
* `travel.summarize_memories`
* `travel.list_reservations`
* `travel.list_checklist_items`
* `travel.list_packing_items`
* `travel.summarize_budget`
* `travel.list_memos`
* `travel.summarize_review`
* `travel.find_related_photos`

更新系:

* `travel.create_wishlist_item`
* `travel.convert_wishlist_to_spot`
* `travel.update_trip`
* `travel.add_participant`
* `travel.add_spot`
* `travel.update_spot`
* `travel.update_spot_status`
* `travel.mark_spot_visited`
* `travel.mark_spot_skipped`
* `travel.add_move`
* `travel.update_move`
* `travel.mark_move_completed`
* `travel.add_event`
* `travel.update_event`
* `travel.add_reservation`
* `travel.update_reservation`
* `travel.add_checklist_item`
* `travel.complete_checklist_item`
* `travel.add_packing_item`
* `travel.mark_packing_packed`
* `travel.add_budget_item`
* `travel.update_budget_item`
* `travel.add_memo`
* `travel.create_memory`
* `travel.update_memory`
* `travel.create_review`

初期MCP Tool化は読み取り系を優先する。更新系はTrust Before Automationに従い、提案、確認、実行の流れを基本にする。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。Trip / Outing中心に、Candidate Spot、Timeline、Cover Image、Memoryを画面表示しやすい関係にしている。
2. API / Toolとして利用できるか
   * 利用できる。Entityごとに読み取り系、更新系のAPI/Tool候補を分けている。
3. 将来MCP Tool化できるか
   * できる。まず読み取り系ToolをMCP化し、更新系は確認、権限、監査を通す方針にできる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。UI専用ではなく、Trip IDを中心にしたTool境界で整理している。
5. UI依存のロジックになっていないか
   * なっていない。TimelineはViewとして扱い、保存データはSpot、Move、Event、Memoに分けている。
6. 読み取り系か更新系か
   * 全体はmixed。最小実装とMCP化は読み取り系から始め、更新系は段階的に追加する。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。Participants、位置情報、子ども情報、Memory、写真候補、共有範囲、外部Place画像、Reservation、Budgetは確認、権限、監査、プライバシー配慮を前提にする。
