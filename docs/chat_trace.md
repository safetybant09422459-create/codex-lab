# Jarvis Chat Trace Bundle v1

## 目的

Jarvis Chatの1ユーザー発言を、Context AssemblyからFinal Answerまで観測し、Developer画面から失敗段階、モデル、Token Usage、所要時間、コード版を調査できるようにする。Traceは診断用の観測であり、LLM判断、Provider / Operation選択、RuntimeのPermission / Confirmation / Audit、Tool結果、会話状態を変更しない。

## 保存範囲

process-localメモリのスレッドセーフなリングバッファへ新しい順で最大50ターンを保持する。サービス再起動で全件消える。DB、ファイル、artifact、会話本文を含むログへは保存しない。Trace記録の失敗はChat本体の結果や例外を置き換えない。

保存する環境情報はGit SHA / branch / dirty、サービス開始時刻、Python / OpenAI SDK版、Jarvis app title、設定モデルと推論設定である。API key、Authorization、Cookie、Developer Token、環境変数一覧、`.env`は保存しない。Git情報は起動時に一度取得し、失敗時はnullにする。

## Pipeline Stage

`turn_started`、`context_assembly`、`operation_catalog`、`llm_call_1`、`action_validation_1`、`runtime_execution`、`observation_build`、`llm_call_2`、`action_validation_2`、`final_answer`、`turn_completed`を個別に記録する。未実行段階は`skipped`であり、成功扱いにしない。

## Token Usage

Responses APIの`usage`から、input、cached input、output、reasoning、total tokenを存在する場合だけ取得する。2回のLLM callをTurn合計へ加算する。欠落値は推測せずnullとし、`LLM_USAGE_MISSING`をinfo候補として残す。料金推定は行わない。

## Redactionと上限

共通sanitizerがdict、配列、tuple、Pydantic model、例外を再帰処理し、secret系キー、Bearer / Authorization / Cookie、credential入りURL、OpenAI key形式を`[REDACTED]`へ置換する。元オブジェクトは変更せず、binaryと未知objectは保存しない。

個別fieldと配列を制限し、切り詰め時は`_truncated` / `_original_bytes` / `_preview`または`_items_truncated` / countを残す。相談用Bundleは約40KB、完全Bundleは約200KBを上限とする。

## Anomaly Flags

例外categoryとStageの観測結果だけを使う決定的ルールで、LLM request / timeout / refusal / incomplete / usage欠落、Action validation、Observation後のOperation、同一Operation再選択、Runtime / Permission / Confirmation、Observation欠落・失敗、Final LLM / Action / Answer、Turn未完了を候補表示する。原因を断定せず、自然言語の意図解釈やLLMによる原因推定は行わない。

## Developer API

- `GET /api/developer/chat-traces?limit=1..50`
- `GET /api/developer/chat-traces/{turn_id}`
- `GET /api/developer/chat-traces/{turn_id}/bundle?mode=consultation`
- `GET /api/developer/chat-traces/{turn_id}/bundle?mode=full`
- `DELETE /api/developer/chat-traces`

全API responseは既存middlewareにより`Cache-Control: no-store`となる。Bundleは`text/plain`で返す。

## UIとBundleの使い方

Developer画面の「Chat Trace」タブを開き、Traceを選ぶ。概要、推定異常箇所、Pipeline、各LLM call、Runtime、Observation、Final Answer、Tokens、Timings、Errorsを確認できる。「相談用コピー」はTool schemaや巨大raw resultを要約した診断用Markdown相当text、「完全トレースコピー」は上限付きの詳細JSON、「JSONコピー」は詳細API responseをコピーする。Clipboard APIが失敗したSafariではtextarea fallbackを使う。家族・private情報を含み得るため、外部共有前に内容を確認する。

## v1の制約

永続化、process間共有、料金推定、Trace検索、認証の追加、Permission / Confirmationの新しい解釈は含まない。Runtimeが公開しない安全判定詳細は`not_exposed`として記録し、推測しない。再起動後の過去Traceは復元できない。
