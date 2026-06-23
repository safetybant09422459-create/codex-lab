# Travel Entity Relationship

## 目的

この文書は、Travel SkillのEntity Relationshipを整理する設計メモである。

Travel Skillは、単なる旅行管理ではなくFamily Outing Memory Skillとして扱う。

今回は設計ドキュメントのみを扱う。Runtime、Executor、API、DB、UIは変更しない。

---

## 基本方針

Travelの中心EntityはTrip / Outingである。

Trip / Outingは、家族旅行、日帰りのおでかけ、近場イベント、後から振り返る思い出整理を束ねる集約ルートである。

Trip / Outingの中にはExperienceが時系列で並ぶ。ExperienceがTravel Skillの本体である。

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

Timeline ItemはDB / 既存互換上の保存実体の呼び方である。domain / API / MCP / ToolではExperienceと呼ぶ。

v0.1では既存`travel_timeline_items`をExperienceの保存実体として活かす。Timelineは保存済みExperienceを時刻や`order_no`で並べたViewであり、UI専用ロジックではない。

---

## 用語と責務

| 用語 | 位置づけ | 補足 |
| --- | --- | --- |
| Trip / Outing | 集約ルート | 宿泊旅行、日帰り、近場イベントを含む |
| Experience | ドメイン/API/Toolの正規名 | 家族の体験。Travelの主概念 |
| Timeline Item | DB / 既存互換名 | `travel_timeline_items`に保存される実体 |
| Timeline View | 取得/表示用View | Experienceを時系列に並べた結果 |
| Spot | UI語彙 / Experience Type | `experience_type = spot` |
| Move | UI語彙 / Experience Type | `experience_type = move` |
| Event | UI語彙 / Experience Type | `experience_type = event` |
| Memo | UI語彙 / Experience Type | `experience_type = memo` |

UIでは「タイムライン」「体験」「スポット」「移動」「メモ」を使い分ける。保存モデルやTool境界ではExperienceへ寄せる。

---

## Experience Type

正式enum:

* `spot`
* `move`
* `event`
* `memo`

`spot`は、場所と関係し得る体験である。Google Places参照や住所を持てるが、物理Placeそのものではない。

`move`は、移動中の体験である。移動中にも写真や思い出メモを持てるため、Spotとは別テーブルにせずExperienceのtypeとして扱う。

`event`は、Google Placesや写真に紐づかなくてもTimeline上に置きたい出来事である。

`memo`は、Timeline上に置く短い記録や注意である。独立Memo Entityを作るほどではないがTimelineに出したい内容を扱う。

旧語彙:

* `place_spot`は`spot`へ寄せる
* `experience`はtype名ではなく概念名として扱う
* `item_type`は既存互換名として残し、domain / API / MCPでは`experience_type`と呼ぶ

---

## Relationship 全体像

| 親Entity | 子Entity | 多重度 | 必須/任意 | 補足 |
| --- | --- | --- | --- | --- |
| なし | Wishlist | 独立 | 任意 | Trip作成前の候補 |
| なし | Trip / Outing | 独立 | 必須 | Travelの中心 |
| Trip / Outing | Participants | 1対多 | 任意から開始、実運用では推奨 | 参加者と共有範囲の判断材料 |
| Trip / Outing | Experience | 1対多 | 任意 | Timelineに並ぶ家族の体験 |
| Experience | Photo Link | 1対多 | 任意 | Photo Skill Assetへの参照 |
| Experience | Cover Image | 0..1または1対多 | 任意 | 代表画像または候補履歴 |
| Experience | Memo | 0..1または1対多 | 任意 | 体験メモ、補足 |
| Experience | Memory | 1対多 | 任意 | 思い出として切り出す場合 |
| Trip / Outing | Reservation | 1対多 | 任意 | ホテル、交通、チケットなど |
| Trip / Outing | Checklist | 1対多 | 任意 | 補助機能 |
| Trip / Outing | Packing | 1対多 | 任意 | 補助機能 |
| Trip / Outing | Budget | 1対多 | 任意 | 補助機能 |
| Trip / Outing | Review | 1対多 | 任意 | 補助機能。主役はMemory |

Spot / Move / Eventをv0.1で別テーブル化しない。これらはExperienceのtypeであり、保存実体は`travel_timeline_items`に寄せる。

---

## Photo / Memo / Time / Place

PhotoはExperienceに紐づく。写真Asset、Thumbnail、Immich連携、写真検索はPhoto Skillの責務であり、Travelは採用した参照や候補リンクだけを持つ。

MemoはExperienceの本文や補足として持てる。複数メモ、共有範囲、監査が必要になったら独立Memo Entityを検討する。

TimeはExperienceの予定または実績の時刻である。時刻未確定の場合は`order_no`でTimeline上の順序を補う。

PlaceはExperienceの補助情報である。`experience_type = spot`でも`place_name`や`place_id`が空でよい。`move`や`event`も必要に応じて場所情報を持てる。

---

## Planned / Actual

Travelでは予定と実績を分けて扱う。

| Entity | planned | actual | status例 |
| --- | --- | --- | --- |
| Trip / Outing | planned_start_at, planned_end_at | actual_start_at, actual_end_at | draft, planning, confirmed, in_progress, completed, cancelled |
| Participants | planned参加者 | actual参加者、一部参加 | planned, joined, absent, partial |
| Experience | planned_start_at, planned_end_at | actual_start_at, actual_end_at | draft, candidate, planned, confirmed, in_progress, completed, visited, skipped, cancelled, unplanned, archived |
| Reservation | 予約予定、利用予定 | 利用済み、キャンセル、返金 | needed, booked, paid, used, canceled, refunded |
| Checklist | due_at | completed_at | todo, doing, done, skipped |
| Packing | needed, prepared予定 | packed, used, missing, not_needed | needed, prepared, packed, used, missing, not_needed |
| Budget | planned_amount | actual_amount | estimated, planned, paid, refunded, cancelled |
| Memory | なし | 思い出メモ、写真リンク、子どもの反応 | draft, completed, shared |

planned/actualを分けることで、Jarvisは旅行後に「予定との差分」と「次回への学び」を説明できる。

---

## Experience CRUD方針

Canonical Tool:

* `travel.create_experience`
* `travel.get_experience`
* `travel.update_experience`
* `travel.archive_experience`

Alias / UI shortcut:

* `travel.add_spot`
* `travel.add_move`
* `travel.add_memo`

Aliasは本流ではない。UIや会話で入力を短くするための入口であり、内部では`experience_type`を指定したCanonical Toolへ寄せる。

既存互換:

* `travel.create_timeline_item`は既存互換として残す
* `travel.get_spot` / `travel.get_spot_photos`が存在する場合は既存互換として残し、将来`travel.get_experience` / `travel.get_experience_photos`へ寄せる
* DB上の`travel_timeline_items`はExperienceの保存実体として扱う

Archive方針:

* 物理削除ではなく`archived`状態または`archived_at`による論理アーカイブを基本にする
* Timelineから通常非表示にするが、監査、復元、思い出確認のため保存実体は残す
* 共有済み写真、子ども情報、位置情報を含むExperienceの削除/アーカイブは確認と監査を前提にする

---

## Entity別設計

### Wishlist

WishlistはTrip作成前の「いつか行きたい」候補である。Tripに採用された場合、`experience_type = spot`のExperienceへ変換する。

将来DBテーブル候補: `travel_wishlist_items`

将来Tool候補:

* `travel.list_wishlist_items`
* `travel.create_wishlist_item`
* `travel.update_wishlist_item`
* `travel.convert_wishlist_to_experience`

### Trip / Outing

Trip / Outingは、タイトル、日程、都道府県、参加者、Experience、Cover Image、Photo Link、Memoryを束ねる。

将来DBテーブル候補: `travel_trips`

実装済みTool:

* `travel.create_trip`
* `travel.get_trip`

将来Tool候補:

* `travel.list_trips`
* `travel.update_trip`
* `travel.cancel_trip`
* `travel.summarize_trip`
* `travel.summarize_trip_memories`

### Experience

Experienceは、Trip / Outing内の体験、移動、出来事、Timeline上のメモを表す。

将来DBテーブル候補: 既存`travel_timeline_items`

将来API候補:

* `GET /travel/trips/{trip_id}/experiences`
* `GET /travel/experiences/{experience_id}`
* `POST /travel/trips/{trip_id}/experiences`
* `PATCH /travel/experiences/{experience_id}`
* `POST /travel/experiences/{experience_id}/archive`

将来Tool候補:

* `travel.create_experience`
* `travel.get_experience`
* `travel.update_experience`
* `travel.archive_experience`
* `travel.get_trip_timeline`

### Cover Image

Cover ImageはTrip代表画像またはExperience代表画像である。

Google Places由来の仮画像はTravel + Google Places Adapter側で扱う。家族写真、Immich Asset、Album、ThumbnailはPhoto Skill側で扱う。

将来DBテーブル候補: `travel_cover_images`または`travel_trips.cover_image_ref` / `travel_timeline_items.cover_image_ref`

### Photo Link

Photo LinkはTrip / Outing、Experience、MemoryとPhoto SkillのAsset候補を接続する。

Photo LinkはPhoto AssetをTravelが所有する仕組みではない。写真の正はPhoto Skillにあり、Travelはおでかけ文脈での関連を保持する。

将来DBテーブル候補: `travel_photo_links`

### Memory

Memoryは、思い出メモ、写真、子どもの反応、また見たい場面をまとめる。

ただし、別EntityとしてのMemoryを急いで作る必要はない。写真、メモ、時刻、体験タイトルを持つExperienceが、そのままMemoryとして機能する場合がある。

将来DBテーブル候補: `travel_memories`

### Reservation / Checklist / Packing / Budget / Review

これらは補助機能である。

ReservationやBudgetは副作用とプライバシーリスクが大きいため、更新系Toolでは確認、権限、監査を前提にする。

---

## 他Skillとの境界

### Photo

Travelは写真を所有しない。Trip / Outing、Experience、期間、場所、参加者などの文脈をPhoto Skillへ渡し、候補や採用済み参照を受け取る。

### Google Places Adapter

TravelはGoogle Places APIを直接呼ばない。場所候補、Place詳細、Place画像、画像キャッシュはGoogle Places Adapterが担当する。

### Calendar / Navigation / Finance / Task

Travelは旅行文脈に閉じた予定、移動、予算、確認事項を扱う。汎用Calendar、リアルタイム経路探索、家計簿、日常タスクは別Skill候補である。

### Family / Profile / Access Control

Travel側にはTrip参加時点のスナップショットや共有範囲を持つ。家族全体のプロフィール、長期的な健康情報、権限管理は将来Family/ProfileまたはAccess Control系Skill候補と連携する。

---

## 既存旅行アプリDBとの関係

既存旅行アプリには概ね以下がある。

* travels
* spots
* moves
* travel_timeline_items
* spot代表画像
* travel hero画像
* Immich写真取得

既存互換の扱い:

* `travels`はTrip / Outingとして扱える
* `travel_timeline_items`はExperienceの保存実体として扱う
* 既存の`spots` / `moves`がある場合も、v0.1のdomain/API/ToolではExperienceへ寄せる
* `create_timeline_item`は既存互換Toolとして残す
* `get_spot` / `get_spot_photos`は既存互換として残し、将来`get_experience` / `get_experience_photos`へ寄せる
* Immich写真取得はTravelから切り離し、Photo Skillへ委譲する

v0.1ではSpot / Move / Eventを別テーブル化しない。将来、移動経路、予約、Place正規化、検索性能などの理由が明確になった場合だけ派生テーブルを検討する。

---

## 将来DBテーブル候補まとめ

v0.1の中心:

* `travel_trips`
* `travel_timeline_items`
* `travel_photo_links`
* `travel_cover_images`
* `travel_participants`

将来拡張:

* `travel_wishlist_items`
* `travel_memories`
* `travel_reservations`
* `travel_checklist_items`
* `travel_packing_items`
* `travel_budget_items`
* `travel_memos`
* `travel_reviews`

`travel_spots`、`travel_moves`、`travel_events`はv0.1では作らない。必要になった場合の将来派生テーブル候補として扱う。

---

## 将来API候補まとめ

読み取り系:

* `GET /travel/trips`
* `GET /travel/trips/{trip_id}`
* `GET /travel/trips/{trip_id}/experiences`
* `GET /travel/experiences/{experience_id}`
* `GET /travel/trips/{trip_id}/timeline`
* `GET /travel/trips/{trip_id}/memories`
* `GET /travel/trips/{trip_id}/photo-links`

更新系:

* `POST /travel/trips`
* `PATCH /travel/trips/{trip_id}`
* `POST /travel/trips/{trip_id}/experiences`
* `PATCH /travel/experiences/{experience_id}`
* `POST /travel/experiences/{experience_id}/archive`
* `POST /travel/trips/{trip_id}/memories`

更新系APIは、家族の予定、位置、写真候補、個人情報に影響するため、確認、権限、監査を前提にする。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。ExperienceをTimeline Viewとして並べ、体験、スポット、移動、メモをUIで使い分けられる。
2. API / Toolとして利用できるか
   * 利用できる。Canonical ToolをExperience CRUDへ寄せ、aliasはショートカットとして扱う。
3. 将来MCP Tool化できるか
   * できる。`travel.experience.get/create/update/archive`へ自然に対応できる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。UI状態ではなくTrip IDとExperience IDを中心に扱う。
5. UI依存のロジックになっていないか
   * なっていない。UI語彙は使い分けるが、保存とTool境界はExperienceに寄せている。
6. 読み取り系か更新系か
   * 全体はmixed。Timeline取得はread、Experience作成/更新/アーカイブはwrite。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。子どもの写真、位置情報、参加者、共有範囲、外部Place画像、アーカイブは確認、権限、監査が必要。
