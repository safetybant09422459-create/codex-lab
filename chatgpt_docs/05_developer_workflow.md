# Developer and Codex Workflow

更新日: 2026-06-30

## 作業境界

Jarvis Devの作業ルートは `/mnt/nas/projects/codex-lab`。旧旅行アプリ `/mnt/nas/projects/project` は別プロジェクトであり、参照が必要でも変更しない。

通常の変更フロー:

1. `git status --short` で既存差分を確認する
2. 対象docs、Tool JSON、Executor、Repository、UIの順に正を確認する
3. 依頼範囲だけ変更し、ユーザーの既存差分を保持する
4. リスクに応じたテストを行う
5. `git diff --check` と `git status --short` を確認する
6. 変更ファイル、検証結果、未解決事項、Jarvis Principle Checkを報告する

## docs棚卸しの判断基準

- 設計案と実装済みを分ける
- Toolの実装状態は `tools/*/*.json` のstatusだけでなくExecutor分岐も確認する
- Skill JSONはSkill全体の粗いmetadataであり、Tool実装状態の正とは限らない
- UIが直接DBや外部Adapterへ依存していないか確認する
- 旧互換名とCanonical名を明示する
- Permission / Confirmation / Auditの実コード制約を省略しない

## Developer UI

Jarvis ShellのDeveloper画面にはCodex Prompt、差分レビュー、Commit / Push、Skill / Tool一覧、service操作、Runtime Execute、Audit表示がある。これらは管理者向けであり、Jarvis Chatの一般ユーザー画面と混ぜない。

`POST /api/run` はCodex作業を開始するDeveloper機能で、一般Chat APIではない。`run_codex`、`restart_service` はhigh riskであり、自然文Chatのallowlistへ入れない。

Codex会話はDeveloper backendのprocess-localなSession ManagerがIDを1件だけ保持する。初回は`codex exec`、
継続時は`codex exec resume <SESSION_ID>`を使い、`POST /api/developer/session/new`で保持IDを破棄する。
永続化、一覧、タイトル、履歴管理、Resume一覧、Forkは未実装であり、Developer再起動時に状態は消える。

## 変更時の安全原則

- commit / push / restartは明示依頼なしに行わない
- DB migrationやTool JSON変更は独立タスクとして扱う
- write ToolはRuntimeを迂回しない
- secretをdocs、frontend、audit、model promptへ含めない
- 外部providerへ送る家族データを最小化する
- ChatのTool allowlistはserver-sideで固定し、modelが任意Tool IDを実行できないようにする

## ChatGPT共有docs運用

20ファイル制限では、`00_project_overview.md`、`01_jarvis_constitution.md`、
`02_jarvis_architecture.md`、`06_jarvis_chat_next_phase.md`、`07_activation_rag.md`、
`99_handoff_summary.md` を優先する。Skill実装の詳細が必要な場合だけ、`03`〜`05`、`90_current_status.md`、
既存のSkill別資料やglossaryを追加する。

共有資料を更新する際は、実装日、実装済み、未実装、既知の制約、次の判断事項を残す。API key、実データ、家族情報、Asset IDの実例は含めない。
