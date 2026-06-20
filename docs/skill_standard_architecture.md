# Skill Standard Architecture

## 目的

この文書は、JarvisのSkillを作るときの標準レイヤー構造を定義する。

Travel Skillで確立したRuntime / Executor / Repository / Storageの分離を、Travel固有の設計ではなく、Jarvis全体の標準構造として扱う。

今後Photo Skillや他Skillを作る場合も、この構造を基準にする。

---

## 標準レイヤー

```text
Runtime
↓
Permission / Confirmation / Audit
↓
ExecutorRegistry
↓
SkillExecutor
↓
SkillRepository
↓
Storage または External Adapter
↓
DB / 外部API
```

各Skillはこの流れを基本形にする。

Skillごとの事情で名前は変わってよいが、責務境界は変えない。

例:

```text
TravelExecutor
↓
TravelRepository
↓
SQLiteTravelStorage / TravelSource
```

```text
PhotoExecutor
↓
PhotoRepository
↓
ImmichAdapter
```

---

## 各レイヤーの責務

| layer | 責務 | 持たない責務 |
| --- | --- | --- |
| Runtime | Tool JSONロード、入力検証、権限、確認、監査、Executor呼び出し | Skill固有ドメインロジック、DB詳細、外部API詳細 |
| Permission / Confirmation / Audit | 実行可否、確認要否、監査記録 | Toolごとの業務判断、UI表示、DB操作 |
| ExecutorRegistry | `tool_id` / `skill_id` からExecutorを選ぶ | Toolごとの実行本体、Repositoryロジック |
| SkillExecutor | Tool入出力adapter。Toolごとの分岐、入力変換、Repository呼び出し、Tool応答JSON整形 | DB接続、外部API呼び出し詳細、Skillの中心ロジック |
| SkillRepository | Skillの中心。ドメインロジック、正規化、ユースケース判断、Storage/Adapter隠蔽 | Runtimeの権限確認、UI表示、Tool JSONロード |
| Storage | DB詳細、永続化、SQL、Record変換を隠蔽 | Runtime判断、Tool応答整形、UI表示 |
| External Adapter | 外部API詳細、認証、レート制御、レスポンス正規化を隠蔽 | Skill全体のドメイン判断、UI表示 |

RepositoryはSkillの中心である。

UI、Runtime Executor、MCP Handler、Chat / AI Automationが同じSkillを使う場合も、Repositoryを共通境界として扱う。

---

## 重要ルール

* RuntimeにSkill固有ロジックを書かない
* UIにドメインロジックを書かない
* ExecutorにDBや外部APIの詳細を書きすぎない
* RepositoryをSkillの中心にする
* StorageはDB詳細を隠蔽する
* External Adapterは外部API詳細を隠蔽する
* Skill間連携は相手SkillのTool / API / Repository抽象を経由する
* TravelからImmichを直接呼ばない
* Photo Skillは `PhotoExecutor -> PhotoRepository -> ImmichAdapter` を基本構造にする

---

## Skill間連携

Skill間連携では、相手Skillの内部実装へ直接依存しない。

例えばTravelが写真候補を必要とする場合、TravelはImmich APIやImmich Adapterを直接呼ばない。TravelはPhoto SkillのTool、API、またはRepository抽象を経由して、写真候補やThumbnail参照を受け取る。

```text
TravelRepository
↓
Photo Tool / Photo API / PhotoRepository abstraction
↓
PhotoRepository
↓
ImmichAdapter
```

この形にすると、Immichから別の写真基盤へ移行してもTravelの設計を変えずに済む。

---

## Travel Skillの実例

Travel Runtime v0.1は、この標準構造の実例である。

現在のTravel実装は、Runtimeの安全境界を通り、ExecutorRegistryからTravelExecutorを選び、TravelExecutorがTravelRepositoryを呼ぶ。

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

現在の通常経路は `TravelRepository -> SQLiteTravelStorage -> storage/travel.db` である。`TravelSource` はLegacy、InMemory、Remoteなどの代替データ供給層を表す名前として残すが、通常のlocal DB-backed read/writeは `SQLiteTravelStorage` が担う。

実装済みTravel Read Tool:

* `travel.get_trips`
* `travel.get_trip`
* `travel.get_trip_timeline`

これらは `local_travel_read` として実行され、副作用のない読み取り系である。

実装済みTravel guarded Write Tool:

* `travel.create_trip`
* `travel.create_timeline_item`

これらは `SQLiteTravelStorage` による `storage/travel.db` へのlocal DB-backed writeとして実装済みである。実行条件は以下とする。

* `mode: write`
* `risk_level: medium`
* `confirmation_required: true`
* `audit_required: true`
* `admin` かつ `confirmed: true` の場合のみ実行
* `family` / `guest` は拒否

TravelRepositoryはTripやTimeline Itemを返し、ExecutorはTool応答JSONへ整形する。UIのExperience Card表示、Runtimeの権限確認、Storageの実装詳細はそれぞれ別レイヤーに残す。

---

## Photo Skill v0.1方針

Photo Skill v0.1も同じ標準構造で作る。

```text
Runtime
↓
Permission / Confirmation / Audit
↓
ExecutorRegistry
↓
PhotoExecutor
↓
PhotoRepository
↓
ImmichAdapter
↓
Immich API
```

初期は読み取り系から始める。

候補:

* `photo.search_assets`
* `photo.get_asset`
* `photo.get_thumbnail`
* `photo.list_albums`
* `photo.find_assets_by_time_range`
* `photo.find_assets_near_location`
* `photo.find_assets_for_trip`
* `photo.find_assets_for_spot`

Album作成、Asset追加、共有、削除などの更新系は、家族写真のプライバシーに影響するため、Permission / Confirmation / Auditの方針を固めてから扱う。

---

## 更新候補

docs内で今後見直す候補:

* Runtimeの説明で、実装済みのPermission Engine、Confirmation Engine、Audit Log、ExecutorRegistry、Travel Runtime v0.1を前提に揃える
* 「将来構造」と書かれている箇所のうち、すでに実装済みのTravel Read / Write境界と矛盾するものを更新する
* Travel設計文書で「DB実装前」となっている箇所は、現在のTravel Runtime v0.1と矛盾しないように補足する
* Photo Skill文書のExecutor候補は、`PhotoExecutor -> PhotoRepository -> ImmichAdapter` を中心に整理する
* TravelとPhotoの境界では、TravelからImmichを直接呼ばないことを維持する

Travel write toolsのうち、`travel.create_trip` と `travel.create_timeline_item` は標準構造のguarded write実例として扱う。その他の更新系へ進む場合も、RuntimeのPermission / Confirmation / Auditを通し、ExecutorからRepositoryへ確定済み操作を渡す。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。UIはRepositoryまたはAPIが返すSkillモデルを表示し、ドメインロジックを持たない。
2. API / Toolとして利用できるか
   * 利用できる。ExecutorがTool入出力を担当し、Repositoryを呼ぶ。
3. 将来MCP Tool化できるか
   * できる。MCP HandlerもRepository抽象を呼ぶ構造にできる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。Runtime、ExecutorRegistry、SkillExecutorを通してSkillへ到達する。
5. UI依存のロジックになっていないか
   * ならない。UIは表示と操作入口、Repositoryはドメインロジックを担当する。
6. 読み取り系か更新系か
   * 標準構造は両方に適用する。Travel Runtime v0.1は読み取り系とguarded writeを含み、Photo Skill v0.1方針は読み取り系中心である。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。Travel guarded write、写真、家族情報、位置情報、外部API送信はPermission / Confirmation / Auditを必須の前提にする。
