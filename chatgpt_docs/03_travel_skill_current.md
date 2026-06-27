# Travel Skill Current State

更新日: 2026-06-27

## 結論

TravelはExperience中心モデルへ移行済みで、Trip read、Experience CRUD、Photo連携、代表画像、通常期間外の写真検索まで実装されている。旧Spot / Timeline Item語は互換境界に残るが、新規Chat設計はExperienceを正規語にする。

## レイヤー

```text
RuntimeService
  → TravelExecutor
  → TravelRepository
  → SQLiteTravelStorage
  → storage/travel.db

TravelRepository
  → PhotoRepositoryCandidateProvider
  → PhotoRepository
  → ImmichAdapter
```

Travel UIやChatがDB・Immichへ直接アクセスしてはいけない。旧旅行アプリのDBはLegacy Dataであり、このリポジトリから変更しない。

## Experience中心モデル

Trip / Outingは旅行または家族のおでかけ単位、Experienceはその中の体験単位である。Experience typeは以下の4種。

- `spot`: 場所での体験
- `move`: 移動体験
- `event`: 時間を持つ出来事
- `memo`: タイムライン上のメモ

主なフィールドは `experience_id`、`experience_type`、`trip_id`、`display_title`、`place_name`、`start_at`、`end_at`、`memo`、`status`、`cover_image_id`。DB上では `travel_timeline_items.id` がExperience IDを兼ね、Repositoryが `timeline_item_id` と `experience_id` の両方を返す。

物理削除ではなく `status: archived` とリンクの `status: archived` を使う。

## 実装済みTool

Read:

- `get_trips`
- `get_trip`
- `get_trip_timeline`
- `get_spots`（互換定義。TravelExecutorの明示分岐はない）
- `get_spot`（互換）
- `get_experience`
- `get_trip_photos`
- `get_spot_photos`（互換）
- `get_experience_photos`
- `get_experience_photo_links`
- `get_experience_photo_search`

Write:

- `create_trip`
- `create_timeline_item`（互換）
- `create_experience`
- `update_experience`
- `archive_experience`
- `set_trip_cover_image`
- `set_spot_cover_image`（Experience代表画像の互換名）
- `link_experience_photo`
- `archive_experience_photo_link`

Travel writeはすべてmedium risk、確認必須、監査対象として定義されている。現行Permissionではadminのみ実行可能で、`confirmed: true` も必要である。

## 実装済みHTTP API

- `GET /api/travel/trips`
- `GET /api/travel/trips/{trip_id}`
- `GET /api/travel/trips/{trip_id}/photos`
- `GET /api/travel/spots/{spot_id}`
- `GET /api/travel/experiences/{experience_id}`
- `GET /api/travel/experiences/{experience_id}/photos`
- `GET /api/travel/experiences/{experience_id}/photo-search`
- `GET /api/travel/experiences/{experience_id}/photo-links`
- `POST /api/travel/experiences/{experience_id}/photo-links`
- `POST /api/travel/experiences/{experience_id}/photo-links/{link_id}/archive`
- `PATCH /api/travel/experiences/{experience_id}`
- `POST /api/travel/trips/{trip_id}/experiences`
- `POST /api/travel/experiences/{experience_id}/archive`

これらのTravel APIは内部でRuntime Toolを呼び、安全層を共有する。

## Photo Linkと代表画像

`travel_experience_photo_links` はExperienceとPhoto Assetを疎結合に接続する。リンク種別:

- `linked`: 明示的に関連付けた写真
- `cover`: Experienceの代表写真。1 Experienceにつきactive coverは1件に整理される
- `hidden`: 通常候補から隠す
- `excluded`: 候補から除外する

リンクはAsset本体を所有せず、Immichの `photo_asset_id` を参照する。リンク取得時はRepositoryがthumbnail / preview URLを付与する。Trip / Experienceの既存Cover Imageは `travel_cover_images` と `cover_image_id` でも管理されており、Photo Assetを代表画像として設定できる。

## 写真検索

`get_experience_photos` はExperienceの `start_at` から `end_at` までを検索する。`end_at` がない場合は開始から2時間を使う。`hidden` / `excluded` のactive link対象は通常候補から除外する。

`get_experience_photo_search` はユーザーが指定したISO 8601の `from` / `to` を使うため、通常のExperience期間外も検索できる。結果には既存リンク状態 `linked`、`cover`、`link_state` が付く。時刻はtimezone必須、分単位に正規化され、limitは1〜100、offset paginationに対応する。

## UI実装

`frontend/static/travel.js` はTrip一覧、Trip詳細、Experience作成・詳細・編集、写真候補、Photo Link、期間外検索、追加読み込みを扱う。`frontend/index.html` のTravel画面が入口である。ドメイン判断はRepository / Runtime側に置き、UIは表示と入力に限定する。

## 未実装・制約

- 独立Memory Entityと専用Memory Tool
- 自然文Chat / LLM Tool routing
- 本格認証、家族ごとの共有範囲
- Google Places Adapter本体
- 位置・人物・画像内容による高度な写真検索
- `get_spots` はTool定義があるがTravelExecutorに専用処理がなく、Chat v0.1では使用しない
- `skills/travel/skill.json` の `status: idea` は粗いSkill metadataであり、Toolごとの実装状態とは一致しない
