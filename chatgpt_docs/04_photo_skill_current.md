# Photo Skill Current State

更新日: 2026-06-27

## 責務

Photo Skillは写真Assetの検索・取得・表示URL生成とImmich接続を担当する。Travelは写真を所有せず、Photo Skill境界を通じてAssetを参照する。

```text
PhotoExecutor → PhotoRepository → ImmichAdapter → Immich API
TravelRepository → PhotoRepositoryCandidateProvider ───────┘
```

## 実装済み

Tool:

- `get_photos`: timezone付きISO 8601の `from` / `to` で写真検索
- `get_asset`: Asset IDでメタデータ取得

API:

- `GET /api/photo/assets/{asset_id}/thumbnail`
- `GET /api/photo/assets/{asset_id}/preview`

返却する主な情報は `asset_id`、`taken_at`、`thumbnail_url`、`preview_url`、`source: immich`。Asset詳細ではfilename、width、heightも返す。

環境変数:

- `IMMICH_BASE_URL`
- `IMMICH_API_KEY`
- `IMMICH_TIMEOUT_SECONDS`（default 10）

API keyはserver-sideだけで保持し、Browser、Chat model、ログへ渡さない。

## Travelとの境界

TravelはTrip / Experienceの時間範囲を決め、Photo側へ検索条件を渡す。PhotoはAsset候補を返す。明示リンク、代表写真、hidden / excluded状態はTravelの文脈データなのでTravel側で保持する。

Experience通常検索と期間外検索はTravel Toolとして公開されるが、内部の写真取得はPhotoRepository経由である。これによりImmich以外のバックエンドへ交換可能である。

## Risk / Privacy

Photo readは副作用を持たないが、家族写真、子どもの写真、撮影時刻、位置につながる情報を扱うためmedium risk、audit requiredである。現行Permissionではmedium-risk readをfamily / guestが実行できず、adminだけが実行できる。この制約はChat v0.1の認証・権限設計で解決対象となる。

Chat modelへ送る情報は最小化する。v0.1では画像バイナリやImmich URLを無条件に外部モデルへ送らず、まず安全なメタデータとUI表示用の同一オリジンURLを使う。画像理解を追加する場合は、明示同意、送信対象、保持期間、provider設定を別途決める。

## 未実装

- Album作成・編集・共有
- 顔・人物・位置・タグ検索のTool化
- 写真の削除やvisibility変更
- Chat modelによる画像内容理解
- family単位の実認証・Asset ACL連携

`skills/photo/skill.json` の `status: idea` はTool単位の実装状態を表さない。実装判定はTool JSON、Executor Registry、Executor / Repositoryのコードで行う。
