# Handoff Summary

更新日: 2026-06-27

## 現在地

Jarvis Chat v0.1開始前のdocs棚卸しを実施した。Travelの実装は旧共有資料より進んでおり、Experience CRUD、Photo Link、代表画像、Experience期間外の任意期間写真検索が利用可能である。Chat / OpenAI連携自体は未実装。

## 実装と設計の一致

一致している点:

- Runtime → Executor → Repository → Storage / Adapterの分離
- Experienceを正規語としTimeline ItemをDB互換として残す方針
- TravelとPhoto / Immichの分離
- writeのmedium risk、confirmation、audit
- UIを入口とし、ロジックをRuntime / Repositoryへ置く方針

注意点:

- `chatgpt_docs/10_skill_travel.md` と `90_current_status.md` の旧一覧はExperience系Tool / APIを反映していなかった
- Skill JSONのTravel / Photoは `status: idea` のままだが、ToolとExecutorは実装済み。Skill statusだけで実装判定しない
- `RuntimeService.execute_stub` という名称だが、Weather / Travel / Photoは実Executorを呼ぶ
- Runtime validationは現状required field確認だけで、JSON Schema全体は検証しない
- Permissionはadmin以外をlow-risk readに限定する。写真系medium-risk readは現状adminが必要
- Confirmation UIは一般ユーザー向けには未実装。Chatのwriteにはpending action型確認が必要
- AuditLoggerは現行Runtimeの成功・失敗・blockを記録し、`audit_required` 値もeventに残す
- `get_spots` は定義されているがTravelExecutorの明示分岐がなく、Chat allowlistに含めない

## Chat v0.1推奨スコープ

read中心:

- Trip特定とExperience一覧
- Experience特定
- 通常写真、明示Photo Link、任意期間写真検索
- Trip / Experience情報からの非永続な思い出要約

write:

- `update_experience` のmemo更新だけから開始
- 対象、変更前、変更後を示し、人間の確認操作に束縛した後で実行

UIは最上位Jarvis画面へ置き、Travel詳細は既存Travel画面へdeep linkする。OpenAI APIはserver-sideだけで呼び、Runtimeを迂回しない。

## 次の実装タスク候補

1. Chat v0.1 ADRとthreat model
2. 認証・role mappingとPhoto read権限決定
3. Chat request / response / tool-call schema
4. server-side orchestratorとTool allowlist
5. pending action型confirmation
6. Jarvis画面のChat UI
7. 代表4ユースケースの統合テスト
8. token / Tool call / rate / daily budget制限

## ChatGPTへ渡す推奨8ファイル

1. `00_project_overview.md`
2. `01_principles_and_constitution.md`
3. `02_runtime_and_tools.md`
4. `03_travel_skill_current.md`
5. `04_photo_skill_current.md`
6. `05_developer_workflow.md`
7. `06_jarvis_chat_next_phase.md`
8. `99_handoff_summary.md`

必要に応じて `99_glossary.md` を9番目に追加する。
