# Glossary

## Jarvis

家庭用AIエージェント。

このプロジェクトの主役。旅行、予定、家電、写真、庭、開発支援などの機能をToolとして利用する。

UI上では、複数Skillの情報を統合して今見るべき情報を表示するトップ入口の名前としても扱う。

`Home`とは呼ばない。

## Jarvis Core

Jarvisの中核。

AI Agent、Users、Permissions、Memory、Tool Registry、Runtime、Notifications、Skillsを調停する。

UI画面そのものではなく、Jarvisが何を判断し、どのToolを安全に呼ぶかを管理する層である。

## Jarvis Screen

UI上のトップ画面。

単なる固定ダッシュボードではなく、Jarvis Coreが複数Skillの情報を統合し、今見せるべきものを表示する入口。

現時点では「喋らないJarvis」として扱う。

## Jarvis Shell

Jarvis Web UI全体の共通入口。

ナビゲーション、共通レイアウト、各Skill画面の受け皿、Developer UIへの導線を担当する。

ドメイン判断やTool実行は担当しない。

## Home Skill

Home Control / Home Automation系Skill。

Jarvis本人やトップ画面ではない。

家電、家の状態、消し忘れ、在宅、旅行モードなどを扱う。

現実世界への作用、在宅情報、生活パターンを扱うため高リスクSkill候補である。

## Skill

Jarvisが利用する能力領域。

例:

* Travel
* Photo
* Calendar
* Garden
* Home
* Weather
* Developer

Skillは独立可能であることを目指し、Tool / API / Repository境界を持つ。

## Tool

AIが利用する機能単位。

例:

* `travel.create_trip`
* `travel.get_trip_timeline`
* `photo.get_photos`
* `calendar.get_events`
* `home.get_home_status`

Toolは入力、出力、mode、risk、confirmation、auditを持つ。

## Runtime

Toolを安全に実行するための境界。

Tool JSONロード、入力検証、権限確認、実行前確認、監査、Executor呼び出しを担当する。

## Tool Registry

`tools/*/*.json`にあるTool定義群。

Tool ID、Skill ID、入力schema、出力schema、mode、risk、confirmation、auditなどを定義する。

## Skill Registry

`skills/*/skill.json`にあるSkill定義群。

SkillのID、名前、説明、mode、risk、confirmation、auditなどを定義する。

## ExecutorRegistry

`tool_id`または`skill_id`から実行に使うExecutorを選ぶ層。

Runtime本体にTool固有分岐を増やさないための境界である。

## SkillExecutor

Runtimeから呼ばれるTool実行adapter。

Tool入力をRepository呼び出しへ変換し、Repository結果をTool応答JSONへ整形する。

DBや外部API詳細を持ちすぎない。

## SkillRepository

Skillの中心。

ドメインロジック、正規化、Storage / Adapter隠蔽、ユースケース判断を担当する。

UI、Runtime Executor、MCP Handler、Chat操作から共通利用できる形にする。

## Storage

DB詳細、永続化、SQL、Record変換を担当する層。

例:

* `SQLiteTravelStorage`

Runtime判断、Tool応答整形、UI表示は担当しない。

## External Adapter

外部API詳細、認証、レート制御、レスポンス正規化を隠蔽する層。

例:

* `ImmichAdapter`
* Google Places Adapter

## Permission

操作可能範囲。

現在のRuntime v0.1では、`admin`、`family`、`guest`のroleを使う。

将来はFamily / Profile / Access Controlへ発展する。

## Confirmation

実行前確認。

`risk_level: high`または`confirmation_required: true`のToolは確認が必要。

現時点ではAPIの`confirmed`フラグで扱い、Confirmation UIは未実装。

## Audit

実行、ブロック、失敗などを記録する監査ログ。

写真、予定、旅行、家、開発操作など、家族や現実世界に影響する操作では重要である。

## Mode

ToolやSkillの操作種別。

* `read`: 参照、一覧、集計、提案が中心
* `write`: 作成、更新、削除、確定が中心
* `mixed`: readとwriteの両方を含む

## Risk Level

操作のリスク分類。

* `low`: 表示や軽い参照。副作用やプライバシー影響が小さい
* `medium`: 家族予定、写真、位置、旅行計画などに影響
* `high`: 家電操作、共有、削除、開発操作、外部送信、防犯などに影響

## Travel Skill

家族旅行、日帰りのおでかけ、近場イベントを含むFamily Outing Memory Skill。

Trip / Outingの中に家族の体験を時系列で残す。

## Trip / Outing

Travel Skillで扱う旅行またはおでかけの単位。

宿泊旅行、日帰り、近場イベント、後から振り返る思い出整理も含む。

## Experience

Trip / Outingの中に時系列で並ぶ家族の体験。

Travel Skillの主概念。

Experience Type:

* `spot`
* `move`
* `event`
* `memo`

場所だけでなく、移動中の写真や思い出メモ、Google Placesに紐づかない出来事も含む。

## Timeline Item

ExperienceのDB / 既存互換名。

domain、API、Tool、MCPでは原則Experienceと呼ぶ。

既存`travel_timeline_items`はExperienceの保存実体として扱う。

## Timeline View

保存済みExperienceを時刻や`order_no`で並べた取得/表示結果。

UI専用ロジックではなく、Tool / API / MCPでも利用できるViewである。

## Candidate Spot

計画時に同じ時間帯へ置ける未確定Spot候補。

例:

* 10:00 海遊館
* 10:00 レゴランド
* 10:00 通天閣

採用、削除、時間変更、別時間帯への移動ができる。

## Cover Image

TripやExperienceの代表画像参照。

source例:

* Google Places由来の仮画像
* Google Places Adapterによりキャッシュ済みの画像
* Photo Skill経由で選んだ家族写真
* 手動指定の画像参照

Google Places由来の仮画像はPhoto Assetではない。

## Photo Link

Travel文脈とPhoto Assetをつなぐ関連。

種類:

* 明示リンク
* 推定リンク

推定リンクは候補であり、確認前に確定データや共有対象にしない。

## Memory

Jarvisの人格や家族の思い出を形成する情報。

Travel文脈では、写真、メモ、時刻、体験タイトル、子どもの反応、また行きたい理由などを含む。

Jarvis全体では、Vision、Decision、Lessons、Preferences、Important EventsもMemoryに含む。

## Photo Skill

家族写真を扱うSkill。

Asset、Album、Search、Thumbnail、Immich Adapterを担当する。

Travel専用ではない。

## Asset

Photo Skillが扱う写真の単位。

Immich Asset IDやメタデータ、Thumbnail / Preview URLと対応する。

## Album

写真のまとまり。

Photo Skillが扱う。TravelはTripに関連するAlbum候補を問い合わせることはあるが、Albumの正はPhoto側に置く。

## Immich Adapter

Immich API連携の境界。

APIキー、認証、検索、Asset取得、Thumbnail取得、レスポンス正規化を担当する。

Travelは直接呼ばない。

## Google Places Adapter

Google Places APIを利用するためのAdapter。

現時点ではPlace Skillを作らず、Travelが必要とする場所検索、場所詳細、場所画像、画像キャッシュをAdapterとして扱う。

## Place Skill

現時点では作らない。

Travel以外の複数Skillが共通Placeモデルを必要とした時に再検討する。

## Calendar Skill

家族の予定を扱うSkill。

今日の予定、朝の予定要約、出発時間通知、家族スケジュール統合、プライバシーレベルを扱う。

## Garden Skill

家庭菜園や植物管理を扱うSkill。

水やり、作業タスク、成長記録、病害虫診断、開花予測などへ拡張する。

## Developer Skill

Jarvis開発支援のSkill / Tool候補。

Codex実行、service restart、git状態、diff、将来のPR作成などを扱う。

高リスクSkillである。

## Weather Skill

天気を扱うSkill。

現在は`local_weather_stub`として動作する読み取り系low risk Skill。

## AI Provider

AIモデル提供元。

例:

* OpenAI
* Claude
* Gemini
* Local AI

Jarvisは特定Providerに依存しない。

## Vision

Jarvisが目指す未来。

長期目標であり、未来のAIが設計思想を理解するための材料。

## Decision

重要な設計判断。

なぜその判断をしたかを記録し、未来の人間やAIへの説明責任を果たす。

## Lesson

失敗や経験から得た学び。

Jarvisの人格形成と将来判断に利用する。

## Idea Backlog

実装未定のアイデア保管庫。

思いついたら記録する。実装順は問わない。忘れないことを優先する。

## Trust

ユーザーがJarvisを信頼するための考え方。

透明性、説明責任、履歴管理、確認、監査を重視する。

## Safari First

iPhone / Safariを主要利用環境として扱う方針。

Chromeで動いてもSafariで壊れるfrontendは未完成として扱う。

## Jarvis Principle Check

1. Web UIから利用できるか: 用語統一によりWeb UI設計で利用できる。
2. API / Toolとして利用できるか: Tool名、Entity名、mode、risk判断の基準になる。
3. 将来MCP Tool化できるか: MCP化時の語彙統一に使える。
4. Jarvis Coreから呼び出せるか: Core / Runtime / Skill境界の共通語彙として使える。
5. UI依存のロジックになっていないか: UI語彙とdomain語彙を分けている。
6. 読み取り系か更新系か: 文書は読み取り系。
7. 副作用・権限・プライバシー上の注意はあるか: 用語の混同は権限境界の混同につながるため、特にHome、Photo、Travel、Calendarで注意する。
