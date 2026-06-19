# Travel Schema v0.1

## 目的

この文書は、Travel Skillの最初の実装に向けた新Travel DBの正規スキーマ設計である。

今回は設計のみを扱う。Runtime、Executor、API、DB、Migration、UIは変更しない。

既存の`/mnt/nas/projects/project/travel.db`はLegacy Dataとして扱う。新Travelの正規スキーマは、既存DBから移行できることを歓迎するが、既存DBの構造には引っ張られない。

---

## 前提

確定方針:

* TravelとPhotoは分離する
* TravelはImmichを持たない
* Place Skillは作らない
* Google Places Adapterを利用する
* Travelは家族旅行だけでなく日帰りおでかけも扱う
* Timelineの主役はPlaceではなくExperienceである
* 現行DBは将来的に廃止予定である

実データでは、既存のSpotが以下のような体験名として使われている。

* 朝散歩
* オルカショーでずぶ濡れ
* 初めての海
* 帰ろう
* ピカピカナイト
* まいハーフバースデー

したがって、新TravelではSpotを物理的なPlaceとして正規化するのではなく、Timeline ItemをExperienceとして扱う。

---

## v0.1の中心Entity

v0.1で必須Entityとして扱うもの:

* Trip
* Timeline Item
* Photo Link
* Participant
* Trip Participant
* Cover Image参照

v0.1で必須Entityにしないもの:

* Packing
* Budget
* Reservation
* Checklist
* 汎用Place

これらはTravelの主役ではないため、将来拡張として扱う。

---

## Entity Relationship

```text
Trip
├ Timeline Item
│  ├ Photo Link
│  └ Cover Image Ref
├ Trip Participant
│  └ Participant Snapshot
└ Cover Image Ref
```

補足:

* Tripは旅行、おでかけ、近場イベントを束ねる単位である。
* Timeline ItemはTrip内の体験、移動、出来事を表す。
* Photo Linkは写真を所有せず、外部Photo Assetへの参照だけを持つ。
* Participantは人物の正規情報ではなく、Travelで使う参加者参照とスナップショットを持つ。
* Cover ImageはTripまたはTimeline Itemの代表画像参照であり、画像本体はTravelが所有しない。ただしGoogle Places由来の仮画像キャッシュはGoogle Places Adapter側の責務として扱う。

---

## Trip

### 目的

Tripは、家族旅行、日帰りおでかけ、近場イベントを含むTravelの集約ルートである。

宿泊旅行に限定しない。例えば「マリンワールド日帰り」「近所の公園で朝散歩」「じいじばあばと誕生日会」もTripとして扱える。

### テーブル候補

`travel_trips`

| field | type | required | note |
| --- | --- | --- | --- |
| `id` | text | yes | Travel内の安定ID。UUIDなど |
| `title` | text | yes | 家族が見るタイトル |
| `start_date` | date | no | 日付単位の開始日 |
| `end_date` | date | no | 日付単位の終了日。日帰りは`start_date`と同じ |
| `prefectures` | json | no | 都道府県配列。複数県移動を許容 |
| `outing_type` | text | no | `overnight_trip`, `day_trip`, `short_outing`, `event` |
| `status` | text | yes | `draft`, `planning`, `confirmed`, `in_progress`, `completed`, `cancelled` |
| `cover_image_id` | text | no | 採用中のCover Image参照 |
| `memo` | text | no | 旅行全体のメモ |
| `privacy_level` | text | yes | `private`, `family`, `shared` |
| `created_by` | text | no | 作成者。将来Family/Profile連携 |
| `created_at` | datetime | yes | 作成日時 |
| `updated_at` | datetime | yes | 更新日時 |

### 設計判断

`start_date` / `end_date`を必須にしない。思い出整理では「去年の夏」「日付不明の写真から作るTrip」があり得るためである。

`prefectures`は配列で持つ。旅行や移動は複数都道府県にまたがるため、単一都道府県に閉じない。

`outing_type`はTripとOutingを別Entityに分けないための分類である。日帰りおでかけも宿泊旅行も同じTimeline構造で扱える。

---

## Timeline Item

### 目的

Timeline ItemはTravel v0.1の主役である。

物理的な場所ではなく、Trip内で家族が体験した、または体験したいことを表す。

### テーブル候補

`travel_timeline_items`

| field | type | required | note |
| --- | --- | --- | --- |
| `id` | text | yes | Timeline Item ID |
| `trip_id` | text | yes | 親Trip |
| `item_type` | text | yes | `spot`, `move`, `event` |
| `display_title` | text | yes | 体験として表示するタイトル |
| `place_name` | text | no | Google Placesや住所検索で使う場所名 |
| `place_id` | text | no | Google Places Adapterから得たProvider Place ID |
| `category` | text | no | `aquarium`, `park`, `meal`, `show`, `walk`, `hotel`, `transport`など |
| `start_at` | datetime | no | 予定または実績の開始時刻 |
| `end_at` | datetime | no | 予定または実績の終了時刻 |
| `time_kind` | text | no | `planned`, `actual`, `estimated`, `unknown` |
| `status` | text | yes | `candidate`, `planned`, `confirmed`, `visited`, `skipped`, `cancelled`, `unplanned` |
| `cover_image_id` | text | no | 採用中のCover Image参照 |
| `memo` | text | no | 体験メモ |
| `order_no` | integer | no | 時刻未確定時の手動順序 |
| `created_at` | datetime | yes | 作成日時 |
| `updated_at` | datetime | yes | 更新日時 |

### item_type

`spot`

場所と関係し得る体験。物理Placeそのものではない。

例:

* オルカショーでずぶ濡れ
* 初めての海
* 朝散歩

`move`

移動を表す。Google Placesに紐づかないことが多い。

例:

* 家を出発
* 新幹線で博多へ
* 帰ろう

`event`

場所や移動ではなく、Trip内の出来事を表す。

例:

* ピカピカナイト
* まいハーフバースデー
* 雨なので予定変更

### 設計判断

Spot、Move、Eventを別テーブルに分けず、v0.1ではTimeline Itemに統合する。

理由:

* 実データ上、SpotがPlaceではなくExperienceとして使われている
* Timeline表示、Tool応答、Memory生成では共通フィールドが多い
* 初期実装で過剰な正規化を避けられる
* 将来、MoveやReservationが複雑化した場合だけ派生テーブルを追加できる

---

## display_title / place_name

### 問題

Travelでは、家族に見せたい名前とGoogle Places検索に使いたい名前が一致しない。

例:

| field | value |
| --- | --- |
| `place_name` | マリンワールド海の中道 |
| `display_title` | オルカショーでずぶ濡れ |

`display_title`だけではGoogle Places検索や写真位置推定が弱くなる。一方で`place_name`だけを主役にすると、実データにある「朝散歩」「初めての海」のような体験が失われる。

### v0.1の方針

`display_title`を必須、`place_name`を任意にする。

Timelineの主役は常に`display_title`である。`place_name`は検索、地図、Google Places Adapter、写真推定のための補助情報として扱う。

### 入力負荷を増やさない案

入力時は1つのタイトルだけで作成できるようにする。

入力例:

```text
オルカショーでずぶ濡れ
```

保存時:

* `display_title`: `オルカショーでずぶ濡れ`
* `place_name`: 未設定
* `place_id`: 未設定

後からGoogle Places候補を選んだ場合:

* `display_title`: `オルカショーでずぶ濡れ`
* `place_name`: `マリンワールド海の中道`
* `place_id`: Google Places Adapter由来のID

Google Placesから先に作った場合:

* `display_title`: 初期値として`place_name`をコピー
* `place_name`: Google Placesの名称
* `place_id`: Google Places Adapter由来のID

ユーザーが体験名に変えた場合:

* `display_title`: ユーザーが編集した体験名
* `place_name`: 元のPlace名を保持

### 補助ルール

* `display_title`は家族に見せる名前であり、短く感情が残る名前を許容する。
* `place_name`は外部Place検索向けの名前であり、正式名称に寄せる。
* `display_title == place_name`でもよい。
* `place_name`が空でもTimeline Itemは有効である。
* `place_id`が空でもTimeline Itemは有効である。
* `place_id`はGoogle Places AdapterのProvider IDであり、Travel内の主キーではない。

この方針により、入力負荷は1フィールドのまま、必要になった時だけPlace情報を補完できる。

---

## Photo Link

### 目的

Travelは写真を所有しない。Photo LinkはTimeline Itemと外部写真Assetの接続だけを表す。

### テーブル候補

`travel_photo_links`

| field | type | required | note |
| --- | --- | --- | --- |
| `id` | text | yes | Photo Link ID |
| `trip_id` | text | yes | 親Trip。Trip全体の写真候補にも使う |
| `timeline_item_id` | text | no | 紐づくTimeline Item。Trip全体リンクでは空を許容 |
| `asset_id` | text | yes | Photo Skill側のAsset ID |
| `source` | text | yes | `immich`, `local`, `manual`, `photo_skill` |
| `link_type` | text | yes | `manual`, `time_range`, `location`, `album`, `cover_image`, `memory_candidate` |
| `confidence` | real | no | 推定リンクの確信度 |
| `visibility` | text | yes | `private`, `family`, `shared` |
| `created_by` | text | no | 明示リンク作成者 |
| `created_at` | datetime | yes | 作成日時 |

### 設計判断

`timeline_item_id`は任意にする。Trip全体に紐づく写真候補、Album由来の写真、Cover Image候補を扱うためである。

`source`は写真基盤の種類を表すが、TravelがImmich APIを直接扱うことはない。`source = immich`はPhoto Skill側のAsset由来を説明するためのメタ情報に留める。

推定リンクは`confidence`を持ち、共有やCover Image採用の前にユーザー確認を必要とする。

---

## Participants

### 目的

Participantsは、Tripに誰が参加したかを表す。

将来「一緒に行った旅行だけ共有」を実現するため、Tripと人物の関係を正規化する。

### テーブル候補: participant master

`travel_participants`

| field | type | required | note |
| --- | --- | --- | --- |
| `id` | text | yes | Travel内Participant ID |
| `display_name` | text | yes | パパ、ママ、結衣、麻衣、じいじ、ばあば |
| `person_ref` | text | no | 将来Family/Profile SkillのPerson ID |
| `relationship` | text | no | `parent`, `child`, `grandparent`, `relative`, `friend` |
| `default_visibility` | text | yes | `private`, `family`, `shared` |
| `created_at` | datetime | yes | 作成日時 |
| `updated_at` | datetime | yes | 更新日時 |

### テーブル候補: trip participant

`travel_trip_participants`

| field | type | required | note |
| --- | --- | --- | --- |
| `id` | text | yes | Trip Participant ID |
| `trip_id` | text | yes | 親Trip |
| `participant_id` | text | yes | Participant参照 |
| `display_name_snapshot` | text | yes | 当時の表示名 |
| `role` | text | no | `owner`, `participant`, `guest`, `viewer` |
| `participation_status` | text | yes | `planned`, `joined`, `partial`, `absent` |
| `share_allowed` | boolean | yes | このTripを本人に共有可能か |
| `created_at` | datetime | yes | 作成日時 |

### 設計判断

Participant MasterとTrip Participantを分ける。

理由:

* 同じ人物が複数Tripに参加する
* Tripごとに参加状態や共有可否が異なる
* 将来Family/Profile Skillと接続しやすい
* 表示名変更後も、当時の呼び名をTripに残せる

「一緒に行った旅行だけ共有」は、`travel_trip_participants`を共有判断の材料にする。

例:

* じいじが参加したTripだけ、じいじに共有候補として出す
* ばあばが参加していないTripは、明示許可なしに共有しない
* 子どもの写真を含むTripは、共有前にPhoto側の権限確認を必要とする

本格的な認証、家族アカウント、閲覧権限はTravelではなくFamily/ProfileまたはAccess Control系の責務とする。

---

## Cover Image

### 目的

Cover Imageは、TripまたはTimeline Itemの代表画像を表す。

計画時はGoogle Places由来の仮画像を使える。旅行後は家族写真へ差し替えてもよいし、差し替えなくてもよい。

### テーブル候補

`travel_cover_images`

| field | type | required | note |
| --- | --- | --- | --- |
| `id` | text | yes | Cover Image ID |
| `owner_type` | text | yes | `trip`, `timeline_item` |
| `owner_id` | text | yes | Trip IDまたはTimeline Item ID |
| `image_source` | text | yes | `google_places`, `photo_asset`, `local`, `manual` |
| `image_ref` | text | yes | Adapter cache key、Photo Asset ID、local pathなど |
| `source_provider` | text | no | `google`, `photo_skill`, `manual`など |
| `status` | text | yes | `placeholder`, `cached`, `family_photo`, `manual`, `archived` |
| `attribution` | text | no | Google Places画像などの帰属 |
| `selected_by` | text | no | 選択者 |
| `selected_at` | datetime | no | 選択日時 |
| `created_at` | datetime | yes | 作成日時 |

### 状態遷移

計画時:

```text
google_places placeholder
  -> google_places cached
```

旅行後:

```text
google_places cached
  -> photo_asset family_photo
```

または:

```text
google_places cached
  -> google_places cached
```

つまり、家族写真へ差し替えない状態も正当な最終状態である。

### 設計判断

Cover ImageをTripやTimeline Itemの単純な文字列フィールドだけにしない。画像の出所、状態、帰属、差し替え有無がTravelの説明可能性とプライバシーに関係するためである。

ただし、TripやTimeline Itemには現在採用中の`cover_image_id`を持たせる。これにより一覧表示やTool応答で代表画像を取りやすくする。

---

## Legacy DBとの関係

### 移行できるもの

既存DBから移行できる可能性が高いもの:

* 旅行タイトル -> `travel_trips.title`
* 旅行開始日、終了日 -> `travel_trips.start_date`, `travel_trips.end_date`
* 都道府県、地域情報 -> `travel_trips.prefectures`
* 既存Spot名 -> `travel_timeline_items.display_title`
* 既存SpotのGoogle Places ID相当 -> `travel_timeline_items.place_id`
* 既存Spotの場所名相当 -> `travel_timeline_items.place_name`
* 既存Spot画像 -> `travel_cover_images`
* 既存Move -> `travel_timeline_items` with `item_type = move`
* 既存メモ -> TripまたはTimeline Itemの`memo`
* 既存写真参照 -> `travel_photo_links`

### 既存DBに存在しない、または弱いもの

新Travelで明示的に必要になるもの:

* `display_title`と`place_name`の分離
* Experience中心のTimeline Item
* `item_type = event`
* Trip参加者と共有判断
* Photo Linkの明示リンク、推定リンク、確信度
* Cover Imageの出所、状態、差し替え有無
* Privacy / Visibility
* Trip全体のOuting種別

### 移行時の考え方

Migration実装はこの文書では扱わない。

将来移行する場合の原則:

* Legacy DBは読み取り専用の入力として扱う
* 既存Spot名はまず`display_title`へ移す
* 既存Place情報がある場合だけ`place_name` / `place_id`へ補完する
* 体験名かPlace名かを自動判定しすぎない
* 推定した値には`confidence`や`source`を残す
* 共有範囲は安全側に倒し、初期値は`private`または`family`にする
* 写真リンクは確定リンクと推定リンクを分ける
* 移行後にユーザーが編集して体験名を整えられるようにする

---

## 5年後のJarvisを見据えた不足候補

過剰設計を避けるため、v0.1では必須にしない。ただし、将来の追加余地としてスキーマ上の逃げ道を残す。

### Memory

旅行後の価値はTimeline Itemだけでなく、写真、感想、子どもの反応を含むMemoryにある。

v0.1ではTimeline Itemの`memo`とPhoto Linkで代替できる。将来、以下が必要になったら`travel_memories`を追加する。

* 子どもの反応
* また行きたい理由
* ハイライト生成
* 家族共有向けの説明文
* 写真スライドショー

### Source / Audit

AIやToolが更新するなら、誰が、なぜ、どの情報源から作ったかが重要になる。

v0.1では`created_by`, `created_at`, `updated_at`, `source`, `confidence`を最小限持つ。将来は監査ログを別Entityにする。

### Planned / Actual

予定と実績を厳密に分けると属性が増える。

v0.1では`start_at`, `end_at`, `time_kind`, `status`で表現する。実運用で差分分析が必要になったら、`planned_start_at`, `actual_start_at`などへ拡張する。

### Sharing Grant

「一緒に行った旅行だけ共有」はTrip Participantで判断できるが、実際の閲覧権限は別概念である。

将来は`travel_share_grants`またはAccess Control Skillを追加し、Trip、Timeline Item、Photo Link、Memoryごとの共有を扱う。

### External Reference

Google Places以外の外部参照が増える可能性がある。

v0.1では`place_id`を単純に持つ。将来、複数Providerを扱う場合は`travel_external_refs`を追加する。

### Reservation / Budget / Checklist

主役ではないためv0.1では作らない。

ただし、旅行計画の実用性が必要になったら、Timeline Itemに任意で紐づく補助Entityとして追加する。

---

## 正規スキーマまとめ

v0.1の推奨テーブル:

* `travel_trips`
* `travel_timeline_items`
* `travel_photo_links`
* `travel_participants`
* `travel_trip_participants`
* `travel_cover_images`

最小実装をさらに小さくする場合:

* 必須: `travel_trips`, `travel_timeline_items`
* 次点: `travel_cover_images`
* その次: `travel_photo_links`, `travel_participants`, `travel_trip_participants`

ただし、家族共有を見据えるならParticipants系は早めに入れるべきである。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。Trip一覧、Timeline、Experience Card、参加者、Cover Image選択に使える。
2. API / Toolとして利用できるか
   * 利用できる。Trip取得、Timeline取得、Timeline Item作成、Cover Image選択、Photo Link候補取得の境界にできる。
3. 将来MCP Tool化できるか
   * できる。特に読み取り系の`travel.list_trips`、`travel.get_timeline`、`travel.get_trip_summary`から始めやすい。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。UI状態ではなくTrip ID、Timeline Item ID、Participant IDを中心にしている。
5. UI依存のロジックになっていないか
   * なっていない。Cover Imageやdisplay_titleは表示にも使うが、Travelの記憶文脈そのものとして定義している。
6. 読み取り系か更新系か
   * スキーマ全体はmixed。初期Toolはread中心にし、作成、差し替え、共有はwriteとして確認を必要とする。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。子どもの写真、位置情報、参加者、共有範囲、Google Places画像の帰属、推定Photo Linkの扱いに注意が必要である。
