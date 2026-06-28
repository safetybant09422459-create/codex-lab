# Travel Skill

## 目的

Travel Skillは、家族旅行、日帰りのおでかけ、近場のイベントを含む「家族のおでかけ記憶」を扱うSkillである。

旅行やおでかけに関する意思決定、候補Spot、移動、Timeline上の出来事、メモ、写真との紐付けを整理し、Jarvisが家族の計画と振り返りを手伝える状態にする。

Travelは写真そのものを管理しない。旅行中や旅行後に写真を利用することはあるが、写真の保存、検索、サムネイル生成、Immich連携はPhoto Skillに委譲する。

Skill名は現時点ではTravelのままとする。ただし文書上のTripは、宿泊旅行だけでなく日帰りのおでかけも含むため、必要に応じてTrip / Outingと表現する。

---

## 概念定義

Travel Skillは、単なる旅行管理ではなくFamily Outing Memory Skillである。

Trip / Outingは、家族旅行、日帰りのおでかけ、近場イベント、後から振り返る思い出整理を束ねる単位である。

Experienceは、Trip / Outingの中に時系列で並ぶ家族の体験であり、Travel Skillの本体である。場所だけが思い出ではない。移動中にも写真や思い出メモは残り、Google Placesにも写真にも紐づかない出来事も家族の記憶になる。

Experience Typeは以下の4種類を正規enumとする。

* `spot`: 場所と関係し得る体験。物理Placeそのものではない
* `move`: 移動中の体験。写真、メモ、時刻、表示タイトルを持てる
* `event`: 出発、到着、チェックイン、家族内の節目などの出来事
* `memo`: Timeline上に置く短い記録や注意

Timeline Itemは、DB / 既存互換上の保存実体の呼び方である。ドメイン、API、Tool、MCPでは原則Experienceと呼ぶ。既存DBや互換ToolではTimeline Itemという名前を残す。

Photo / Memo / Time / Placeの関係:

* PhotoはExperienceに紐づけられる。写真の保存、検索、Thumbnail、Immich連携はPhoto Skillに委譲する
* MemoはExperienceの本文や補足として持てる。独立Memo Entityが必要になるまではExperienceの`memo`で扱う
* TimeはExperienceの予定または実績の時刻であり、時刻未確定時は手動順序で補う
* PlaceはExperienceの補助情報である。`spot`でも`place_name`や`place_id`が空でよい

UIでは文脈に応じて「タイムライン」「体験」「スポット」「移動」「メモ」を使い分ける。保存/API/Toolの主概念はExperienceであり、UI上の見せ方だけで別Entityを増やさない。

---

## 扱う対象

Travelが扱う主な対象:

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

これらは「家族のおでかけ体験」を構成する情報であり、家族が旅行前、旅行中、旅行後に確認・更新する対象である。

Checklist、Packing、Budget、SouvenirはTravelの主役ではない。扱う場合も補助機能であり、現時点の核はTrip / Outing、Experience、Cover Image、Photo Link、Memoryである。

---

## 責務

Travelの責務:

* 行きたい場所をWishlistとして管理する
* Trip / Outingを作成し、タイトル、日程、都道府県、参加者を整理する
* 旅行やおでかけに参加する家族メンバーをParticipantsとして扱う
* 同じ時間帯に並ぶ未確定候補をCandidate Spotとして管理する
* 訪問候補、採用済み地点、訪問済み地点、行かなかった地点を`spot` Experienceとして管理する
* 時間制約のある移動予定や移動実績を`move` Experienceとして管理する
* Google Placesや写真に紐づかない出来事を`event` ExperienceとしてTimelineに置けるようにする
* Timeline上で見せたい短い記録を`memo` Experienceとして管理する
* ExperienceをTimeline Itemとして保存し、Timeline上に表示できるようにする
* ホテル、交通、レストラン、チケットなどのReservationを管理する
* 出発前のChecklist、家族ごとのPacking、旅行予算と実績を補助情報として管理する
* 旅行中の気づきや注意点をMemoとして残す
* 旅行後の思い出、子どもの反応、また行きたい場所をMemoryとして残す
* Trip代表画像とSpot代表画像をCover Imageとして扱う
* Google Places Adapterから取得した仮画像をCover Image候補として利用する
* 旅行に関連する家族写真が必要な場合、Photo Skillへ問い合わせる
* Google仮画像を、実際に撮影した家族写真へ置き換えた参照を保持する

家族のおでかけでは、単に場所を並べるだけでは不十分である。

子どもの体力、移動時間、休憩、候補の相談、当日まで決まらないSpot、家族写真、思い出メモまで含めて、Travelは「おでかけが記憶として残るための情報」を扱う。

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
* Immich写真をGoogle Places仮画像と同じAssetとして保存すること
* Calendar全体の予定管理
* Navigation全体の経路探索
* Weather全体の天気管理
* 家計簿全体の管理
* 家庭内在庫や日常タスク全体の管理

Travelは、旅行に必要な外部情報を利用することはある。

ただし、写真、天気、地図、予定、通知などの横断的な領域をTravel内に抱え込まない。

---

## UI Experience Principle

Travel Web UIでは、現行アプリのTimelineカード体験を失わない。

この体験は、星野リゾートやホテルの「過ごし方」ページのように、全面画像、中央に大きく表示される体験タイトル、左上の時計アイコン、時刻表示、縦に並ぶカードによって、旅行前はワクワクする計画画面、旅行後は家族の思い出を振り返るMemory画面にする考え方である。

詳細は[Travel UI Experience Principle](travel_ui_experience.md)に置く。

重要なのは、これはWeb UI向けの表示原則であり、MCP Tool、Chat、APIに同じ見た目を強制しないことである。一方で、Tool/APIが返すデータには、UIがこの体験を再現できるだけの`title`、`display_title`、時刻、`cover_image`、`experience_type`、`participants`、`memo`、`linked_photos`などを含められるようにする。

---

## Photoとの関係

TravelはPhotoを利用する側である。

例:

* このTrip / Outingに関連する写真を取得したい
* このSpot周辺で撮影された写真を探したい
* このMove時間帯に撮影された写真を探したい
* この旅行期間中の写真を候補として表示したい
* Memoryに使う写真候補を出したい
* Google仮画像を家族写真へ置き換える候補を出したい

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

Google Places由来の仮画像はPhoto SkillのAssetではない。TravelはTrip代表画像やSpot代表画像として仮画像参照を持てるが、家族が撮影した写真はPhoto SkillのAssetとして扱い、Travelは採用された参照だけを保持する。

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

Google Places画像は、計画時のワクワク感を作るための仮画像として重要である。旅行後に家族写真へ置き換える場合もあるが、置き換えずGoogle仮画像のまま残る場合もある。

---

## Candidate Spot

計画時には、同じ時間帯に複数のSpot候補が並ぶ。

例:

* 10:00 海遊館
* 10:00 レゴランド
* 10:00 通天閣

これらは重複データではなく、家族で相談するための未確定計画である。

Spotの状態例:

* `candidate`: 候補。まだ採用していない
* `planned`: 予定に置いたが、まだ確定ではない
* `confirmed`: 採用済み
* `visited`: 実際に行った
* `skipped`: 行かなかった
* `cancelled`: 中止した
* `unplanned`: 予定外に立ち寄った

Candidate Spotは削除、採用、時間変更、別時間帯への移動ができる前提にする。旅行当日まで`candidate`のまま残るSpotがあってもよい。

---

## Experience / Timeline Item

TimelineはExperienceを時系列に並べた表示であり、spotとmoveだけでは構成しない。

「お家出発！」のように、Google Placesにも写真にも紐づかないがTimeline上に置きたい出来事がある。

Travel UIにおけるExperienceは、単なるPlace CardではなくExperience Cardとして表示される。これまでSpotと呼んでいたものも、実際には「朝散歩」「オルカショーでずぶ濡れ」「初めての海」のような体験タイトルを持つ。

そのため、Experienceは「場所」だけでなく「体験」を表現できる必要がある。たとえば`place_name = マリンワールド`、`display_title = オルカショーでずぶ濡れ`のように、物理的な場所名とUI向け体験タイトルを分けられる設計にする。

Experience Type:

* `spot`: Google Places参照を持つ、または場所として扱う体験
* `move`: 新幹線、飛行機、予約済み交通など時間制約のある移動体験
* `event`: 出発、到着、チェックイン、家族内の節目など、場所Assetや写真がなくても置きたい出来事
* `memo`: Timeline上で見せたい短いメモ

Moveは主に時間制約がある移動を書く。座席番号や予約番号などの詳細は、ReservationまたはExperienceのMemoに残す。

DB上は既存の`travel_timeline_items`をExperienceの保存実体として活かす。`item_type`は既存互換名として残し、domain / API / MCPでは`experience_type`と呼ぶ。新規設計では`spot`, `move`, `event`, `memo`を正式enumとし、`place_spot`や`experience`は旧語彙または表示上の説明として扱う。

TimelineはExperienceの保存実体から生成される表示順Viewであり、UI専用ロジックではない。Jarvis CoreやMCP Toolからも、同じExperienceをTimelineとして取得できるようにする。

---

## Experience CRUD方針

Canonical ToolはExperienceを主語にする。

* `travel.create_experience`
* `travel.get_experience`
* `travel.update_experience`
* `travel.archive_experience`

Alias / UI shortcutとして以下を置ける。

* `travel.add_spot`
* `travel.add_move`
* `travel.add_memo`

ただしaliasは本流ではない。UIや会話で入力を短くするためのショートカットであり、内部では`experience_type`を指定したCanonical Toolへ寄せる。

既存互換:

* `travel.create_timeline_item`は既存互換Toolとして残す
* `travel_timeline_items`はExperienceの保存実体として扱う
* `travel.get_spot` / `travel.get_spot_photos`が存在する場合は既存互換として残し、将来`travel.get_experience` / `travel.get_experience_photos`へ寄せる
* v0.1ではSpot / Move / Eventを別テーブル化しない

Archive方針:

* Experienceの削除は物理削除ではなく`archived`状態または`archived_at`による論理アーカイブを基本にする
* Timelineから通常非表示にするが、監査、復元、思い出確認のため保存実体は残す
* 共有済み写真、子ども情報、位置情報を含むExperienceの削除/アーカイブは確認と監査を前提にする

CRUD実装前の未決事項:

* `status` enumを単一にするか、`experience_type`別に許容状態を制限するか
* `visited`と`completed`を併存させるか、`spot`以外も含めて`completed`へ寄せるか
* `archived`を`status`で表すか、`archived_at`のみで表すか
* `planned_start_at` / `actual_start_at`を最初から持つか、v0.1は`start_at` / `end_at` / `time_kind`で始めるか
* `memo`をExperience内フィールドに留めるか、複数メモ対応の独立Entityを同時に作るか
* `get_experience_photos`の戻り値をPhoto Skill参照のみにするか、推定候補も含めるか

---

## Cover Image

Cover Imageには2種類ある。

* Trip代表画像
* Spot代表画像

Cover Imageは、Travel UIで「いつ・誰が・何をした」を直感的に思い出すための重要な情報である。計画時はGoogle Places由来の仮画像がワクワク感を作り、旅行後は家族写真へ置き換えることでMemoryとしての価値が高まる場合がある。

Cover Imageの状態:

* Google Places由来の仮画像
* Google Places Adapterによりローカル保存またはキャッシュ済みの画像
* 実際に撮影した家族写真へ置き換えた画像
* 置き換えずGoogle仮画像のまま残る画像

責務境界:

* Google Places由来の仮画像取得とキャッシュはTravel + Google Places Adapter側
* 家族が撮影した写真、Immich Asset、Album、ThumbnailはPhoto Skill側
* TravelはTripやSpotのCover Imageとして採用された参照を保持する
* TravelはPhotoの内部ID体系やImmich APIを直接知らない

---

## Memory

旅行後の価値は、単なるReviewではなくMemoryである。

ここでいうMemoryはTravelが所有するTrip / Outing内の思い出文脈であり、Jarvis全体の長期Memoryや
Memory Skillそのものではない。TravelはJarvis Memoryから参照されるEvidenceを提供し、何を
長期MemoryにするかはJarvis Coreが判断する。境界の詳細は
[Jarvis Memory Architecture](memory_architecture.md)を参照する。

Memoryは以下をまとめる。

* 思い出メモ
* その時間帯や場所で撮影された写真
* 子どもの反応
* ここが良かった、また行きたいという記録
* 次に家族で見返したい場面

写真、メモ、時刻、体験タイトルが揃っている場合、Experience自体がMemoryとして機能することがある。別EntityとしてのMemoryを急いで作る必要はなく、共有範囲、複数写真、独立した要約などが必要になった段階でMemory Entityを使えばよい。

Experienceの時刻や場所から、その時撮った写真候補をPhoto Skillへ問い合わせる。MemoryはTrip全体、Experience、Participantに紐づけられる。

将来は「去年の旅行ハイライト見せて」のような要求に対して、テレビや大画面に画像と思い出メモを流せるようにする。この場合も写真の保存と権限はPhoto側、どの思い出を流すかの文脈はTravel側に置く。

---

## Sharing / Access Control

将来、じいじばあばにも旅行やおでかけのMemoryを見せたい。

ただし、家族全体の旅行や写真をすべて見せるのではなく、一緒に行ったTrip / Outingだけを見せたい。

設計上の注意:

* Participantsは表示権限の判断材料になる
* Tripごとに共有範囲を持てるようにする
* Memory、Memo、Photo LinkはTripの共有範囲より狭い可視性を持てるようにする
* 推定Photo Linkや子どもの写真を自動公開しない
* 共有は本格実装まで読み取り中心で考え、更新や外部共有は確認と監査を必須にする

---

## Tool候補

実装済みguarded write Tool:

* `travel.create_trip`
* `travel.create_timeline_item`

将来のTool候補:

* `travel.create_wishlist_item`
* `travel.list_wishlist_items`
* `travel.update_trip`
* `travel.add_participant`
* `travel.add_spot`
* `travel.search_spot_candidates`
* `travel.update_spot_status`
* `travel.set_spot_cover_image`
* `travel.add_move`
* `travel.add_event`
* `travel.get_timeline`
* `travel.add_reservation`
* `travel.list_reservations`
* `travel.add_checklist_item`
* `travel.complete_checklist_item`
* `travel.add_packing_item`
* `travel.assign_packing_item`
* `travel.add_budget_item`
* `travel.summarize_budget`
* `travel.add_memo`
* `travel.create_memory`
* `travel.summarize_memories`
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
* 「去年何したっけ？」
* 「岡山から子ども連れで無理のない移動計画を作って」
* 「予約漏れがないか見て」
* 「旅行後に写真候補と一緒に思い出をまとめて」
* 「去年の旅行ハイライトを見せて」

MCP Tool化する場合も、TravelはPhotoやGoogle Placesの実装詳細を隠す。

Jarvis Coreから見るTravelは「おでかけの計画と記憶を扱うTool」であり、写真管理サービスやGoogle APIの薄いラッパーではない。

---

## 設計メモ

Travelは家族のおでかけ記憶の文脈を持つ。

同じSpotでも、家族旅行では以下が重要になる。

* 子どもが楽しめるか
* 移動が長すぎないか
* 休憩できるか
* 雨の日でも成立するか
* 予約が必要か
* 荷物が増えすぎないか
* 写真を後で振り返りやすいか

* 同じ時間帯の候補を家族で見比べられるか
* 当日まで未確定の候補を残せるか
* 「お家出発！」のような出来事をTimelineに置けるか
* Google仮画像と家族写真の違いを保てるか
* 旅行後に写真と思い出メモを一緒に見返せるか

この文脈をTravelに残し、写真管理や外部Place APIの詳細は別責務に分ける。
