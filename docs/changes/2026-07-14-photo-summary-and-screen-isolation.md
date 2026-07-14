# Photo Recent Summary / Screen Isolation（2026-07-14）

## 実施日時

2026-07-14（Asia/Tokyo）

## 変更内容

* Photo Providerの既存`get_recent_photos`をRuntime経由で利用する`GET /api/photo/recent-summary`を追加した。
* Photoプレースホルダーを、期間選択付きのread-onlyメタデータ概要画面へ置き換えた。
* Consumer向けレスポンスから写真本体、asset ID、座標、人物名、Adapter生エラーを除外した。
* Photo UIを独立moduleにし、Photo画面を開いた時だけ取得するようにした。
* shellに画面変更eventを追加し、Developer UIと保護APIの初期取得をDeveloper画面を開くまで遅延した。

## 変更理由・判断理由

ゼロベースでは、写真の一覧をすぐ作る案、会話だけでPhotoを使う案、メタデータ概要を作る案を比較した。
家族が日常的に価値を感じつつ、人物・位置・写真内容の公開範囲をまだ設計し切っていない段階でも安全に出せるのは、
既存Providerの観測事実を最小開示する概要だった。これはAI Firstを損なわず、UIに写真選定や意味判断を持たせない。

Developerの一括初期化は、Consumer画面を使うだけでも高リスクPlaneのAPIへ接続する構造だった。
process分離前でも画面単位に起動境界を置くことで、一般利用の失敗分離と将来の別bundle化を進められる。

## 参考資料

* Jarvis `docs/principles.md`、`docs/architecture.md`、`docs/photo.md`
* Immich公式API documentation（OpenAPI契約、scoped API key、header認証）
* Immich公式Features（Memories、multi-user、map、face recognition等。Jarvis側ではそのまま公開せず最小開示を優先）

## 採用案

* Provider / Runtimeを正本とし、Consumer APIは表示に必要な事実だけを投影する。
* 写真表示より先に、接続状態とメタデータ概要を安全に提供する。
* 各画面のmoduleは自画面が表示された時だけ外部依存を読み込む。

## 不採用案

* Immich thumbnailの即時表示: 家族・asset単位の可視性とPresentation Contractが未完成。
* UIからImmich APIを直接呼ぶ: Provider Principleに反し、API keyをfrontendへ露出する。
* Pythonで「良い写真」「思い出」を選ぶ: 意味判断を決定的コードへ移すためAI Firstに反する。
* 全画面共通の巨大初期化を維持する: Developer障害がConsumer体験へ波及する。

## 影響範囲

* Backend: Photo Consumer API / response model
* Frontend: Photo画面、shell event、Developer画面の遅延初期化
* Runtime / Provider / Repository / DB schema: 変更なし
* 外部サービスへのwrite: なし

## リスクと制約

* 現在のConsumer APIには本格的なfamily/member認証がない。最小開示だが、家族ネットワーク外へ公開してよい契約ではない。
* `limit`件だけを集計するため、期間内の全写真統計ではない。
* UI bundleとFastAPI processはまだConsumer / Developerで分離されていない。遅延初期化はprocess分離の代替ではない。
* ImmichのAPI変更へはAdapter contract testで追随する必要がある。

## ロールバック方法

DB変更はない。Photo route/model/module/markup/styleを除去し、Developer初期化を従来の即時実行へ戻せる。
ただし後者は一般画面の障害分離を悪化させるため推奨しない。

## 次段階

1. household/member principalとPhoto visibility policyをserver-sideで導入する。
2. scoped read-only Immich API keyの起動時検証とAdapter contract testを追加する。
3. Presentation Contractを設計し、明示可視性を満たすthumbnailだけを返す。
4. Consumer Plane / Developer Planeを別process・port・Unix user・frontend bundleへ分離する。
