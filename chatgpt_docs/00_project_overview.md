# Jarvis Project Overview

更新日: 2026-06-27

## この資料の用途

このディレクトリは、ChatGPT Projectへアップロードして設計・実装相談に使うための共有資料である。設計案と現在の実装を混同しないため、各資料では `実装済み`、`制約`、`次フェーズ案` を分ける。

## Jarvisとは

Jarvisは、家族の日常、旅行、写真、予定、家、開発作業を自然な対話から扱うPersonal AI Systemを目指す。AIはデータや外部サービスを直接操作せず、Jarvis Coreが選んだToolをRuntimeのPermission、Confirmation、Auditを通して実行する。

```text
Web / Chat / Voice / MCP
        ↓
Jarvis Core（意図理解、Tool選択、応答構成）
        ↓
Runtime（Validation、Permission、Confirmation、Audit）
        ↓
Tool Registry → Executor Registry → Skill / Repository / Adapter
```

## 現在地

Jarvis Dev v0.3には次がある。

- FastAPIとモバイル向けJarvis Shell
- JSONベースのSkill Registry / Tool Registry
- Runtime APIとPermission / Confirmation / Audit
- Weather、Travel、Photoの実Executor
- Travelの新SQLite DB、Experience中心モデル、CRUD
- Photo Skill境界を通したImmich写真検索
- Experience Photo Link、代表写真、通常期間外の任意期間検索
- Travel Web UIでの旅行・Experience・写真の表示と更新

Calendar、Garden、Home、DeveloperにはTool定義やUI導線があるが、Runtime Executor Registryで実Executorが登録されているのはWeather、Travel、Photoである。未登録SkillはStubExecutorへフォールバックする。

## Travelの現在地

Travelのドメイン上の中心はExperienceである。DB互換のため `travel_timeline_items` と `timeline_item_id` が残るが、API / Tool / UIでは `experience_id` と `experience_type` を正規語として使う。

実装済みの中心機能:

- Trip一覧・詳細・タイムライン
- Experienceの取得・作成・更新・論理アーカイブ
- `spot` / `move` / `event` / `memo` のExperience type
- Trip / Experienceの代表画像
- ExperienceとImmich Assetの明示リンク
- `linked` / `cover` / `hidden` / `excluded` のリンク状態
- Experience時間帯の写真候補と任意期間の追加検索
- Photo Linkの論理アーカイブ

## 次フェーズ

Jarvis Chat v0.1では、既存Toolを自然文から安全に呼び出す。最初の対象はTravel readを中心とし、`update_experience` は実行前確認を必須にする。詳細は `06_jarvis_chat_next_phase.md` を参照する。

## 正とする資料

- 思想・憲法: `01_principles_and_constitution.md`
- RuntimeとRegistry: `02_runtime_and_tools.md`
- Travel現状: `03_travel_skill_current.md`
- Photo現状: `04_photo_skill_current.md`
- 開発運用: `05_developer_workflow.md`
- Chat v0.1案: `06_jarvis_chat_next_phase.md`
- 引き継ぎ: `99_handoff_summary.md`

詳細な根拠はリポジトリの `docs/`、`skills/`、`tools/`、`backend/`、`frontend/` にある。ChatGPTへ渡す際は上記8ファイルを優先する。
