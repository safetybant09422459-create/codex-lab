# Jarvis Chat v0.1 Design Material

更新日: 2026-06-27

## 目的

Jarvis Chat v0.1は、ユーザーの自然文を既存Travel Toolへ安全に接続し、結果を会話と既存Travel UIで確認できる最小実装である。新しいTravelロジックをChat内に作らず、Jarvis CoreがToolを選び、Runtimeが実行を統制する。

v0.1の成功条件:

- 日本語の代表4ユースケースを扱える
- readは根拠となるTool結果に基づいて応答する
- writeは対象・変更内容を提示し、ユーザー確認後だけ実行する
- Tool結果と最終応答を会話単位で追跡できる
- 既存Travel画面へ遷移・再表示できる
- コスト、Tool回数、入力サイズ、タイムアウトに上限がある

## 最初の自然文とTool flow

### 「福岡旅行の体験一覧を見せて」

1. `get_trips` で候補を取得
2. title、prefectures、dateから福岡旅行を特定
3. 曖昧なら候補を提示して選択を求める
4. `get_trip_timeline` でExperience一覧を取得
5. `display_title`、時刻、type、memo概要を表示し、Travel画面への導線を出す

`get_trips` 自体に検索引数はないため、モデルが勝手なtrip_idを作らない。

### 「アンパンマンミュージアムの写真を見せて」

1. 会話中のtrip / experience contextを優先
2. 不足時は `get_trips` → `get_trip_timeline`
3. Experienceを特定し `get_experience` で確認
4. `get_experience_photo_links` で明示リンクとcoverを取得
5. `get_experience_photos` で通常時間帯の候補を取得
6. 必要な場合だけ、明示した期間で `get_experience_photo_search` を使う

同名Experienceが複数ある場合は確認する。写真バイナリをLLMへ送ることと、Browserにthumbnailを表示することを分離する。

### 「この体験にメモを追加して」

1. 「この体験」が指す `experience_id` を会話contextから解決
2. `get_experience` で現在のmemoを取得
3. 追記後の全文と対象Experienceをpreviewする
4. ユーザーが明示確認
5. `update_experience` に `experience_id` と新しい `memo` を渡す
6. 成功結果を表示しTravel詳細を再取得する

「追加」は既存memoを上書きしないよう、現在値とのマージ結果を確認画面に出す。対象や本文が曖昧なら実行しない。

### 「旅行の思い出を要約して」

1. 対象Tripを特定
2. `get_trip` と `get_trip_timeline` を取得
3. 必要なExperienceだけ `get_experience_photo_links` / `get_experience_photos` を取得
4. Tool結果の範囲で、体験順、メモ、代表写真、ハイライトを要約

現状は専用Memory Entity / summary Toolがないため、要約文はLLM生成物でありDBへ保存しない。写真の内容理解は未実装なので、撮影時刻やリンク情報だけから画像内容を断定しない。

## v0.1 Tool allowlist

Read:

- `get_trips`
- `get_trip`
- `get_trip_timeline`
- `get_experience`
- `get_experience_photos`
- `get_experience_photo_links`
- `get_experience_photo_search`

Write:

- `update_experience` のうち、v0.1ではmemo更新を第一対象に限定

`create_*`、archive、Photo Link更新、cover更新、Developer / Home Toolはv0.1 allowlist外とする。Tool allowlistと引数制約はserver-sideで強制する。

## write確認方針

現行Runtimeは `admin` と `confirmed: true` でTravel writeを許可するが、Chatでは単なるBooleanをmodelに設定させてはいけない。

推奨フロー:

```text
modelがwrite案を作る
  → serverがTool / target / before / afterを正規化
  → pending_action_idを発行（短い期限、single use）
  → UIが差分と影響を表示
  → 人間が確認ボタンを押す
  → serverが同一payloadをRuntimeへconfirmed=trueで渡す
  → Auditと結果を表示
```

確認は会話の「はい」だけに依存せず、対象ID、Tool ID、引数hash、user/session、期限へ束縛する。確認後にmodelが引数を変更した場合は再確認する。

## Chat UI配置

Jarvis Shellの最上位 `Jarvis` 画面へ、独立したChat panel / screenとして置く。Travel画面内に置くと将来のCalendar、Photo、Home横断会話を妨げるためである。

推奨構成:

- Jarvis画面: 会話、確認カード、Tool実行状態、エラー
- Travel画面: 詳細なTrip / Experience / 写真表示と編集
- Chat応答: Experience cardと「Travelで開く」deep link
- Developer画面: raw Tool result、Audit、debug。一般ユーザーには出さない

モバイルSafariを第一対象とし、送信中断、再送、長い結果の折りたたみ、写真lazy loadを考慮する。

## API境界案

Chat固有のHTTP endpointを追加し、そのserver-side orchestratorだけがOpenAI APIとRuntimeへ接続する。BrowserからOpenAIへ直接接続しない。

概念的なAPI:

- `POST /api/chat/messages`: user message送信
- `GET /api/chat/conversations/{id}`: 会話取得
- `POST /api/chat/pending-actions/{id}/confirm`: write確認
- `POST /api/chat/pending-actions/{id}/cancel`: cancel

会話保存をv0.1に含めるかは要決定。保存するなら本文、Tool call、Tool result、確認、user、timestampの保持期間と削除方針を先に決める。

## OpenAI API環境変数案

- `OPENAI_API_KEY`: server-only secret
- `JARVIS_CHAT_MODEL`:使用model
- `JARVIS_CHAT_TIMEOUT_SECONDS`
- `JARVIS_CHAT_MAX_INPUT_TOKENS`
- `JARVIS_CHAT_MAX_OUTPUT_TOKENS`
- `JARVIS_CHAT_MAX_TOOL_CALLS`
- `JARVIS_CHAT_MAX_REQUESTS_PER_MINUTE`
- `JARVIS_CHAT_DAILY_BUDGET_USD`
- `JARVIS_CHAT_PER_REQUEST_BUDGET_USD`
- `JARVIS_CHAT_STORE_CONVERSATIONS`: 保存有無
- `JARVIS_CHAT_RETENTION_DAYS`: 保存時の保持日数

model名や価格は変わるためコードへ固定せず、導入時に公式情報で確認する。API keyをfrontend、Tool result、Auditへ含めない。

## コスト上限と安全設計

- 1 turnの入力・出力token上限
- 1 turnのTool call上限（初期値3〜6程度を検討）
- 同一引数の繰り返しTool callを拒否
- request / user / day単位のrate limitとbudget
- 会話履歴を要約して送信量を抑制
- Tool resultのfield allowlist、件数、文字数上限
- 写真はthumbnail表示とmodel送信を分離
- prompt injectionを含むTool resultを命令として扱わない
- server-side Tool allowlistとschema validation
- timeout、cancel、partial failure表示
- OpenAI障害時にwriteを実行しないfail-closed
- Auditへsecretや写真binaryを記録しない

## 実装前に解決する事項

1. 実ユーザー認証とrole mapping。現行family / guestはmedium-risk photo read不可
2. pending action型確認をどこに保持するか
3. conversation保存有無とretention
4. modelとAPI方式、構造化Tool call schema
5. 写真をmodelへ送るか、UI表示だけにするか
6. Trip / Experienceの曖昧一致とcontextの失効ルール
7. Runtimeのrequired-field-only validationをfull schema validationへ強化する範囲
