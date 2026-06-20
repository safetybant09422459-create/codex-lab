# Decision: Skill Standard Architecture

## 日付

2026-06

---

## 背景

Travel Skillでは、Runtime / Executor / Repository / Storage の責務境界を分ける設計が固まってきた。

Travel Runtime v0.1では、Runtimeの安全境界を通り、ExecutorRegistryからTravelExecutorを選び、TravelExecutorがTravelRepositoryを呼ぶ構造になっている。読み取りToolに加えて、一部のguarded write Toolも同じ標準構造で実装済みである。

今後Photo Skillや他Skillを作るときに、Skillごとに構造がばらつくと、Jarvis Core、Web UI、Tool、MCP化、権限、監査の境界が崩れやすい。

---

## 決定

JarvisのSkillは、以下を標準レイヤー構造とする。

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

RepositoryをSkillの中心にする。

RuntimeはTool JSONロード、入力検証、権限、確認、監査、Executor呼び出しを担当する。

ExecutorRegistryは `tool_id` / `skill_id` からExecutorを選ぶ。

SkillExecutorはTool入出力adapterとして、Toolごとの分岐、Repository呼び出し、Tool応答JSON整形を担当する。

SkillRepositoryはSkillの中心として、ドメインロジック、正規化、Storage/Adapter隠蔽を担当する。

StorageはDB詳細を隠蔽し、External Adapterは外部API詳細を隠蔽する。

---

## ルール

* RuntimeにSkill固有ロジックを書かない
* UIにドメインロジックを書かない
* ExecutorにDBや外部APIの詳細を書きすぎない
* RepositoryをSkillの中心にする
* Skill間連携は相手SkillのTool / API / Repository抽象を経由する
* TravelからImmichを直接呼ばない
* Photo Skillは `PhotoExecutor -> PhotoRepository -> ImmichAdapter` で作る

---

## Travel Skillの位置づけ

Travel Skillの現状は、標準構造の実例である。

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

現在の通常経路は `TravelRepository -> SQLiteTravelStorage -> storage/travel.db` である。`TravelSource` はLegacy、InMemory、Remoteなどの代替データ供給層を表す名前として扱う。

実装済みTravel Read Tool:

* `travel.get_trips`
* `travel.get_trip`
* `travel.get_trip_timeline`

実装済みTravel guarded Write Tool:

* `travel.create_trip`
* `travel.create_timeline_item`

Travel Write Toolは以下の条件で実行する。

* `mode: write`
* `risk_level: medium`
* `confirmation_required: true`
* `audit_required: true`
* `admin` かつ `confirmed: true` の場合のみ実行
* `family` / `guest` は拒否

TravelExecutorはTool入力をTravelRepository呼び出しへ変換し、TravelRepositoryはTrip / Timeline Itemを返す。

TravelはImmichを直接呼ばず、写真が必要な場合はPhoto Skillの抽象を経由する。

---

## Photo Skill v0.1方針

Photo Skill v0.1は、同じ標準構造で作る。

```text
PhotoExecutor
↓
PhotoRepository
↓
ImmichAdapter
```

初期は読み取り系を中心にする。

Album作成、Asset追加、共有、削除などの更新系は、Permission / Confirmation / Auditの扱いを固めてから実装する。

---

## 影響

良い影響:

* Web UI、API、Tool、MCP Toolが同じRepository抽象を共有しやすい
* RuntimeにSkill固有ロジックが増えにくい
* ExecutorにDBや外部API詳細が漏れにくい
* Skill間連携の依存方向が明確になる
* Photo基盤をImmich以外へ変える場合もTravelへの影響を抑えられる

注意点:

* Repositoryが肥大化しすぎないよう、必要に応じて内部ServiceやAdapterへ分ける
* Executorを単なる通過点にしすぎず、Tool入出力のadapter責務は明確に持たせる
* StorageとExternal Adapterは、Skillのドメイン判断を持たない
* write系は必ずRuntimeのPermission / Confirmation / Auditを通す。実装済みTravel guarded writeもこの条件を前提にする

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。UIはAPIやRepository由来のSkillモデルを表示できる。
2. API / Toolとして利用できるか
   * 利用できる。ExecutorがTool境界を担当する。
3. 将来MCP Tool化できるか
   * できる。MCP HandlerはRepository抽象を呼べる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。RuntimeとExecutorRegistryからSkillExecutorへ到達する。
5. UI依存のロジックになっていないか
   * なっていない。ドメインロジックはRepositoryに置く。
6. 読み取り系か更新系か
   * 構造は両方に適用する。現時点のTravel実例は読み取り系とguarded writeを含み、Photo v0.1方針は読み取り系中心である。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。Travel guarded write、写真、位置情報、家族情報、外部API送信は確認と監査を前提にする。
