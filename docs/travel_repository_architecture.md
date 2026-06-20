# Travel Repository Architecture v0.1

## 目的

この文書は、Travel Runtime / Executor / Repository / Storage の責務境界を整理するための設計メモである。

Travel Runtime v0.1では、Runtimeの安全境界、ExecutorRegistry、TravelExecutor、TravelRepository、SQLiteTravelStorageの流れが実装済みである。読み取りToolに加えて、一部のguarded write Toolもこの構造で実装済みである。この文書はその構造をTravel Skillの実例として記録し、今後の追加Toolや外部連携へ進むときの責務境界を明確にする。

この文書自体は設計整理のみを扱う。DB作成、Migration、Runtime Tool追加、Executor追加、API追加、UI追加、Immich連携、Google Places連携、Service Restartは行わない。

Travelの正は、`storage/travel.db` である。既存の`/mnt/nas/projects/project/travel.db`はLegacy Dataであり、移行元、参照元、サンプルとして扱う。TravelExecutorやUIがLegacy DBへ直接依存する構造にはしない。

---

## 1. 全体構成

基本構成:

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
SQLiteTravelStorage / TravelSource
```

各層の意味:

| layer | 役割 | 直接知ってよいもの | 直接知らないもの |
| --- | --- | --- | --- |
| Runtime | Tool JSONロード、入力検証、権限、確認、監査、実行制御 | ExecutorのTool境界 | DBスキーマ詳細、Travel固有ロジック |
| ExecutorRegistry | `tool_id` / `skill_id` からExecutorを選ぶ | Executor登録情報 | Travelのドメイン判断、DBスキーマ詳細 |
| TravelExecutor | Runtimeから呼ばれるTravel Tool実行単位 | Tool入力、TravelRepository、Tool応答JSON | SQLite、Legacy DBパス、UI表示実装 |
| TravelRepository | Travel Skillの中心ロジック | Travelモデル、Storage/Source抽象、Timeline組み立て | Runtime確認UI、SQLite接続詳細、MCP実装詳細 |
| TravelStorage / TravelSource | 永続化、外部データ、Legacy変換 | DB、Legacy DB、メモリ、将来Remote API | Runtime、Tool応答形式、Web UI表示ロジック |

この構成では、Executorは「Tool入力をRepositoryへ渡し、Tool向けJSONを返す」薄い層にする。Travelのデータ取得、Legacy変換、将来のStorage差し替えはRepository以下に閉じ込める。

この構成はJarvis全体の[Skill Standard Architecture](skill_standard_architecture.md)のTravel実例である。

---

## 2. TravelExecutorの責務

TravelExecutorはRuntimeから呼ばれる実行アダプタである。

責務:

* Runtimeから渡されたTool入力を受け取る
* 入力をTravelRepositoryの呼び出しに変換する
* Repositoryから返ったTravelモデルをTool向けJSONに整形する
* Tool名、入力schema、出力schemaの境界を保つ
* RuntimeのPermission / Confirmation / Audit結果に従う

非責務:

* SQLiteへ直接接続しない
* `/mnt/nas/projects/project/travel.db`を直接参照しない
* MigrationやDB作成をしない
* Permission / Confirmation / Auditの判断本体を持たない
* UI表示ロジックを持たない
* ImmichやGoogle Places APIを直接呼ばない

ExecutorはTravelRepositoryの利用者の1つであり、Travel Skillの中心ではない。将来MCP ToolやWeb APIが追加されても、ExecutorだけにTravelロジックが集まらないようにする。

---

## 3. TravelRepositoryの責務

TravelRepositoryはTravel Skillの中心である。UI、Runtime Executor、MCP Tool、Chat操作、将来のAI自動編集から共通利用できる形にする。

実装済みの読み取り責務:

* `get_trips`
* `get_trip`
* `get_trip_timeline`

実装済みのguarded write責務:

* `create_trip`
* `create_timeline_item`

将来の読み取り系候補:

* `get_timeline`

将来の更新系候補:

* `update_trip`
* `update_timeline_item`
* `set_cover_image`
* `link_photo`
* `unlink_photo`

Repositoryが担うこと:

* 新Travel DBのモデルを基準にしたTrip / Timeline Itemを返す
* Timeline ItemをExperience Cardとして再現できる情報に正規化する
* Storage差し替えを隠蔽する
* LegacyTravelSourceから来たデータを新Travelモデルへ変換する
* UI専用ではない、Tool/API/MCPでも使える戻り値にする
* PhotoやGoogle Placesは必要に応じて抽象化されたAdapter/Repository経由で扱う

Repositoryが返すTimeline Itemの基本フィールド:

| field | note |
| --- | --- |
| `id` | Timeline Itemの安定ID |
| `item_type` | `spot`, `move`, `event`, `memo`など |
| `display_title` | Experience Cardの主表示タイトル |
| `place_name` | Google Places、地図、写真位置推定に使う場所名 |
| `place_id` | Google Places AdapterなどのProvider Place ID |
| `category` | `aquarium`, `park`, `meal`, `show`, `walk`, `hotel`, `transport`など |
| `start_at` | 開始時刻。予定、実績、推定を含む |
| `end_at` | 終了時刻 |
| `cover_image` | 代表画像参照。画像本体はTravelが所有しない |
| `memo` | 体験メモ |
| `participants` | Trip参加者またはItem参加者の参照、スナップショット |
| `linked_photos` | Photo Skill側Assetへの参照。Asset本体はTravelが所有しない |

Repositoryの戻り値は、Web UIのExperience Cardを再現できるだけの情報を含む。ただし、時計アイコン、中央配置、カードスタイルなどの見た目はUI側の責務である。

---

## 4. TravelStorage / TravelSourceの責務

TravelStorage / TravelSourceは永続化層またはデータ供給層である。

実装済みまたは候補:

| name | 用途 | 主な責務 |
| --- | --- | --- |
| `SQLiteTravelStorage` | 通常経路のTravel Storage | `storage/travel.db` に対するlocal DB-backed read/write |
| `LegacyTravelSource` | 既存DBのread-only参照、移行元 | Legacy DBを新Travelモデルへ変換して返す |
| `InMemoryTravelSource` | テスト、プロトタイプ、デモ | DBなしでRepository契約を検証する |
| `FutureRemoteTravelSource` | 将来のRemote DB/API | Repository契約を保ったまま外部永続化へ接続する |

Storage / Sourceが担うこと:

* 実データの取得、保存、変換
* DB接続、SQL、Remote API呼び出しなどの実装詳細
* Legacy DBのテーブル構造差分の吸収
* Repositoryへ渡すRaw Recordまたは正規化済みRecordの生成

Storage / Sourceが担わないこと:

* Runtimeの権限判断
* Tool応答JSONの最終整形
* Web UI用の表示レイアウト
* Travel Skill全体のユースケース判断

`TravelStorage`はTravel DBの読み書きを担う名前として使う。現在の通常経路は `TravelRepository -> SQLiteTravelStorage -> storage/travel.db` である。`TravelSource`はLegacy、InMemory、Remoteなど、必ずしも通常DBを正としないデータ供給元にも使える名前として扱う。

---

## 5. 新Travel DBとLegacy DBの関係

新Travel DBが正である。

現在の通常DB:

* path: `storage/travel.db`
* access: `SQLiteTravelStorage`
* scope: local DB-backed read/write

既存DB:

* path: `/mnt/nas/projects/project/travel.db`
* tables: `travels`, `spots`, `moves`, `spot_images`

既存DBはLegacy Dataである。今後作る新Travel DBへ移行できることは歓迎するが、Repository契約や新Travel SchemaをLegacy DBに合わせて縮めない。

Legacy DBとの関係:

| Legacy | 新Travelモデル | 方針 |
| --- | --- | --- |
| `travels` | Trip | 初期Tripデータとして読み取り可能 |
| `spots` | Timeline Item / Spot | 既存spotsはExperienceとして扱う |
| `moves` | Timeline Item / Move | 移動Timeline Itemへ変換する |
| `spot_images` | Cover Image参照 | Photo AssetではなくCover Image参照として扱う |

Legacy `spots.name`の変換方針:

* `spots.name`は新モデルでは原則`display_title`に近い
* Legacy側に明確な場所名がない場合、`place_name`は空または推定不可にする
* Legacy側にGoogle Places相当の場所情報がある場合だけ`place_name`や`place_id`へ変換する
* 「朝散歩」「オルカショーでずぶ濡れ」「初めての海」のような値を物理Place名として無理に正規化しない

LegacyTravelSourceはread-onlyを基本にする。Legacy DBへ書き戻す設計にすると、新Travel DBへの移行責務とLegacy維持責務が混ざるためである。

避ける構造:

```text
TravelExecutor
  ↓
/mnt/nas/projects/project/travel.db
```

採用する構造:

```text
TravelExecutor
  ↓
TravelRepository
  ↓
SQLiteTravelStorage
  ↓
storage/travel.db
```

Legacy参照が必要な場合だけ、Repository配下で `LegacyTravelSource` を使う。

---

## 6. 実装済みTravel Tool

実装済みのread Tool:

| tool | repository method | mode / risk |
| --- | --- | --- |
| `travel.get_trips` | `get_trips` | read / low |
| `travel.get_trip` | `get_trip` | read / low |
| `travel.get_trip_timeline` | `get_trip_timeline` | read / low |

さらに必要になったら追加する候補:

* `travel.get_timeline`
* `travel.list_timeline_items`
* `travel.get_trip_summary`

実装済みのguarded write Tool:

| tool | repository method | mode / risk |
| --- | --- | --- |
| `travel.create_trip` | `create_trip` | write / medium |
| `travel.create_timeline_item` | `create_timeline_item` | write / medium |

Tool応答は、Trip一覧とTripごとのTimelineを返せることを基本にする。Experience Card再現に必要な`display_title`、`place_name`、`start_at`、`end_at`、`cover_image`、`memo`、`participants`、`linked_photos`はRepositoryの返却モデルに含められるようにする。

---

## 7. guarded write Toolの条件

`travel.create_trip` と `travel.create_timeline_item` は実装済みのguarded write Toolである。

実行条件:

* `mode: write`
* `risk_level: medium`
* `confirmation_required: true`
* `audit_required: true`
* `admin` かつ `confirmed: true` の場合のみ実行
* `family` / `guest` は拒否

Trip、Timeline、Photo Link、Participant、Cover Imageは家族の予定、位置情報、写真、思い出に関わるため、更新系はRuntimeのPermission / Confirmation / Auditを必ず通す。AI自動編集を広げる場合も、提案、確認、実行、取り消しの流れを明確にしてから対象Toolを増やす。

---

## 8. UI / MCP / Chat から共通利用する考え方

TravelRepositoryは、Web UI、Runtime Executor、MCP Tool、Chat操作、将来のAI自動編集から共通利用できる境界にする。

利用イメージ:

```text
Web UI
  ↓
Travel API
  ↓
TravelRepository

Runtime Tool
  ↓
TravelExecutor
  ↓
TravelRepository

MCP Tool
  ↓
MCP Handler
  ↓
TravelRepository

Chat / AI Automation
  ↓
Runtime Permission / Confirmation / Audit
  ↓
TravelExecutor or Application Service
  ↓
TravelRepository
```

共通利用の原則:

* UI表示用のカード構成はUIで行う
* Repositoryは表示に必要なTravelモデルを返す
* Tool/MCP向けJSONはExecutorやHandlerで整形する
* Permission / Confirmation / AuditはRuntime側に置く
* RepositoryはStorage差し替えを隠蔽し、呼び出し元へDB種別を漏らさない

これにより、Web UIだけが使えるTravelロジックや、Executorだけが知るDB変換を避ける。

---

## 9. 将来DBを差し替える場合の影響範囲

将来DBを差し替える場合、影響範囲はStorage / Source層に閉じることを目標にする。

例:

| 変更 | 影響させたい範囲 | 影響させたくない範囲 |
| --- | --- | --- |
| Legacy DB参照から通常SQLite DBへ移行 | `LegacyTravelSource`から`SQLiteTravelStorage`への切り替え | Executor、Tool schema、UI |
| SQLiteからRemote APIへ移行 | `FutureRemoteTravelSource`実装、Repository設定 | Executor、MCP Tool、Chat操作 |
| Timeline Itemの保存方法変更 | Storage実装、Repository内の組み立て | RuntimeのPermission / Confirmation / Audit |
| Cover Image参照の保存先変更 | Storage実装、Google Places Adapter連携部 | Tool入力、Experience Cardの基本モデル |

Repository契約を保てば、DB差し替え時にUI、MCP Tool、Runtime Executorを大きく変えずに済む。逆にExecutorが直接SQLiteやLegacy DBを触ると、DB差し替えのたびにTool実装、テスト、権限境界を見直す必要が出る。

---

## 10. Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。RepositoryがTripとTimeline Itemを返し、UIはExperience Cardとして表示できる。
2. API / Toolとして利用できるか
   * 利用できる。ExecutorやAPI HandlerはRepositoryを呼び、Tool/API向けJSONへ整形できる。
3. 将来MCP Tool化できるか
   * できる。MCP HandlerもExecutorと同じくTravelRepositoryを呼ぶ構造にできる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。RuntimeはPermission / Confirmation / Auditを担当し、TravelExecutor経由でRepositoryへ到達できる。
5. UI依存のロジックになっていないか
   * なっていない。Experience Card再現に必要な情報は返すが、カードの見た目やレイアウトはUI側に残す。
6. 読み取り系か更新系か
   * 読み取り系とguarded writeの両方である。実装済みwriteは `travel.create_trip` と `travel.create_timeline_item` に限定し、adminかつconfirmedの場合のみ実行する。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。Trip、Timeline、Participant、位置情報、子どもの写真、Memory、Photo Link、共有範囲はプライバシー対象である。read-onlyでも公開範囲に注意し、write系ではRuntimeの確認と監査を必須にする。
