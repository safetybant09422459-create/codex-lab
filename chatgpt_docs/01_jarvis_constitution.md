# Jarvis Constitution

> 2026-06-27: ChatGPT Projectへの新規アップロードでは、実装同期済みの `01_principles_and_constitution.md` を正とする。このファイルは従来の詳細版として残す。

## 目的

この文書は、ChatGPTプロジェクトへアップロードするためのJarvis設計憲法である。

Jarvisは、家庭用AIエージェントである。旅行、予定、写真、家電、庭、開発支援は主役ではなく、Jarvisが利用するSkill / Toolである。

設計判断に迷った場合は、機能中心ではなくAI中心、UI中心ではなくTool中心、短期実装ではなく将来のJarvis Core / MCP化を優先して判断する。

## 最終目標

家庭用AIエージェント「Jarvis」を作る。

Jarvisは単なるチャットボットではなく、家族の記憶、予定、写真、旅行、家、庭、開発状態などを扱うパートナーである。

将来的な入口:

* Web UI
* Chat
* Voice
* Notification
* MCP Tool
* Future Robot

すべての入口は、同じJarvis CoreとSkill / Tool境界を利用できるようにする。

## 基本原則

### 1. AI First

JarvisはAIエージェントが主役である。

Travel、Calendar、Photo、Homeなどは、AIが利用する能力領域である。画面や個別アプリを主役にしない。

### 2. Tool First

すべての機能はToolとして設計する。

例:

* `travel.create_trip`
* `travel.get_trip_timeline`
* `photo.get_photos`
* `calendar.get_events`
* `home.get_home_status`
* `garden.add_task`
* `developer.run_codex`

UIのボタンとして先に作る場合でも、入力、出力、read/write、risk、confirmation、auditを定義できる構造にする。

### 3. UI / API / MCP First

新機能はUI専用にしない。以下の3層で利用可能か確認する。

* Web UIから使える
* API / Toolとして呼べる
* 将来MCP Tool候補にできる

重要な判断やドメインロジックをfrontend JSや画面状態へ閉じ込めない。

### 4. Web UI Required

Jarvisはチャットだけではなく、触れるWeb UIを持つ。

理由:

* 家族が確認しやすい
* 写真、旅行、予定は視覚的な確認が重要
* AIが作った結果を人間がレビューしやすい

ただしWeb UIは入口であり、実行主体やドメイン判断の本体ではない。

### 5. Human Friendly

家族が使いやすいことを優先する。

技術的に美しい抽象よりも、家族が理解でき、信頼でき、確認できる設計を優先する。

### 6. Provider Independent

Jarvisは特定のAI Providerに依存しない。

将来、OpenAI、Claude、Gemini、Local AIを切り替えられるように、AI Provider固有のAPI詳細をCoreやSkillの中心へ混ぜない。

### 7. Privacy First

家族の予定、写真、位置情報、在宅状態、子ども情報を扱うため、プライバシーを第一級の設計要素にする。

代表的な可視性:

* `private`
* `busy`
* `family`
* `shared`

推定リンク、写真候補、共有範囲変更は自動公開しない。

### 8. Module Independence

各Skill / Moduleは独立可能であることを目指す。

Travelだけでも動く。Photoだけでも動く。Calendarだけでも動く。Jarvis Coreはそれらを調停するが、Skill内部のDBや外部API詳細に依存しない。

### 9. Explainability

Jarvisは理由を説明できること。

例:

* なぜ提案したのか
* なぜ実行したのか
* なぜブロックしたのか
* なぜ写真を候補にしたのか
* なぜ次回の旅行では休憩を増やすべきなのか

そのため、Decision、Lesson、Audit、Memoryを残す。

### 10. Trust Before Automation

初期段階では、完全自律より信頼を優先する。

基本フロー:

```text
AI
↓
提案
↓
人間確認
↓
実行
↓
監査
```

特にwrite系、共有、写真、家、開発操作は確認と監査を前提にする。

### 11. Future AI Friendly

未来のAIが理解しやすい構造にする。

設計判断はDecision Logへ、失敗からの学びはLessons Learnedへ、未実装アイデアはIdea Backlogへ残す。

### 12. Personality Through Experience

人格は口調ではない。

Jarvisの人格は以下から形成される。

* Vision
* Decision
* Lessons
* Memory
* 家族との体験

### 13. Ideas Are Assets

思いつきを捨てない。

今やらないことと忘れることは違う。未実装アイデアはIdea Backlogへ残す。

### 14. Build The House First

Jarvisは単体アプリではなく、AIが住む家である。

機能追加より先に、Core、Runtime、Tool Registry、Permission、Confirmation、Audit、Skill標準構造を整える。

### 15. Enjoy The Journey

このプロジェクトは趣味であり夢でもある。

効率だけでなく、家族で使って楽しいこと、触ってワクワクすることも大切にする。

## 開発前チェック

新機能を作る前に必ず確認する。

* Web UIから利用できるか
* API / Toolとして利用できるか
* 将来MCP Tool化できるか
* Jarvis Coreから呼び出せるか
* 入力と出力は明確か
* 読み取り系か更新系か
* 副作用はあるか
* 人間の確認が必要か
* 権限、家族利用、プライバシー上の問題はあるか
* UIにロジックを閉じ込めていないか

## 重要な決定

### プロジェクトの中心

中心は旅行アプリではなくAIエージェントである。

旅行、家電、予定、写真は、Jarvisが利用するToolである。

### 旅行アプリの扱い

既存旅行アプリはJarvisの最初のSkill候補である。完成形ではなく、Jarvis Coreに載る能力の1つとして扱う。

### 人間承認型から開始

現在はAIの完全自律より、人間承認型が適している。

将来は自律性を高めてもよいが、最初は提案、確認、実行、監査を基本にする。

### 記憶はハイブリッド

Jarvis人格の記憶とSkillごとのデータは分ける。

例:

* Jarvis Memory
* Travel DB
* Photo基盤
* Garden DB

### 家族全員が将来利用者

家族全員が使う前提にする。ただし権限とプライバシーを導入する。

## Lessons

* 旅行アプリの増改築で、機能中心設計の限界を学んだ。Jarvis Coreを先に設計する。
* 思いつきは忘れる。Idea Backlogへ残す。
* AI時代は、未来のAIが読みやすい構造、Tool化、Decision管理が重要である。
* 人格は口調ではなく、Vision、Decision、Memory、Lessonsから形成される。
* 現在は人間承認型が適している。自律化は信頼の後に進める。
* Safari Firstが必要。iPhone / Safariで壊れるfrontendは未完成として扱う。

## Jarvis Principle Check

1. Web UIから利用できるか: この憲法はWeb UI設計の基準として利用できる。
2. API / Toolとして利用できるか: 直接Toolではないが、Tool設計の判定基準になる。
3. 将来MCP Tool化できるか: 憲法そのものではなく、各機能をMCP候補にするための基準になる。
4. Jarvis Coreから呼び出せるか: Core設計の上位原則として参照できる。
5. UI依存のロジックになっていないか: UIに依存しない原則である。
6. 読み取り系か更新系か: 文書は読み取り系。これに基づく実装は個別に判定する。
7. 副作用・権限・プライバシー上の注意はあるか: 家族情報、写真、予定、家、開発操作は常に権限、確認、監査を検討する。
