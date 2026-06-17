# Jarvis Core Architecture

## 目的

Jarvis Coreは、家庭用AIエージェントJarvisの中核である。

旅行、予定、家電、写真、音楽などの機能は、Jarvis Coreから呼び出されるModule / Toolとして扱う。

---

## 基本構造

```text
Jarvis
├ AI Agent
├ Memory
├ Users
├ Permissions
├ Tool Registry
├ Notifications
├ Modules
└ Frontend
```

将来構造：

```text
Jarvis Core
↓
Tool Registry
↓
各Module / MCP Tool
```

Module / MCP Tool候補：

* Travel Tool / MCP
* Calendar Tool / MCP
* Home Tool / MCP
* Photo Tool / MCP
* Developer Tool / MCP

Jarvis Developer は、Jarvis Core本体ではなく、Developer Tool / MCP候補として扱う。

---

## 設計原則

### 1. AIが主役

画面や機能ではなく、AIエージェントが中心。

各機能はAIが使うToolである。

---

### 2. Webアプリ必須

チャットだけではなく、ユーザーが触って確認できるWebアプリを持つ。

理由：

* ワクワク感がある
* 実物を触って判断できる
* 将来AIが作った機能をプレビューできる

---

### 3. Tool First

すべての機能はToolとして設計する。

例：

```text
calendar.create_event
calendar.list_today_events
travel.create_trip
travel.add_spot
appliance.turn_off
photo.show_on_tv
notification.send
```

---

### 4. Moduleは独立可能

各ModuleはJarvis Coreに統合されるが、単体でも動作できるようにする。

例：

```text
modules/travel
modules/calendar
modules/appliance
modules/photo
modules/garden
```

---

### 5. AI Providerは交換可能

Jarvis本体は特定のAIに依存しない。

```text
AI Adapter
├ OpenAI
├ Claude
├ Gemini
└ Local AI
```

---

## 主要コンポーネント

## AI Agent

ユーザーの指示を理解し、必要なToolを選択する。

将来的には以下を行う。

* 提案
* 実行
* 改善
* PR作成
* 自己拡張

---

## Memory

Jarvisの人格と継続性を支える。

記憶は単なる会話ログではない。

扱うもの：

* Vision
* Decision
* Lessons Learned
* User Preferences
* Important Memories
* Past Failures

---

## Users

家族利用を前提とする。

初期ユーザー：

* Owner
* Adult
* Child
* Guest

---

## Permissions

プライバシーと安全性を守る。

例：

```text
private: 本人だけ
busy: 詳細を隠して予定ありだけ表示
family: 家族に表示
shared: 全員に表示
```

コード変更や家電操作など強い権限が必要な操作は、Owner権限を必要とする。

---

## Tool Registry

Jarvisが使えるTool一覧を管理する。

Toolは以下の情報を持つ。

* name
* description
* input schema
* required permission
* risk level
* module name
* enabled / disabled

---

## Notifications

Jarvisからユーザーに知らせる仕組み。

例：

* 朝の予定一覧
* 出発時間通知
* 家電消し忘れ通知
* AI提案通知
* PR作成通知

---

## Modules

各機能単位。

初期候補：

```text
calendar
travel
appliance
photo
music
garden
```

---

## Frontend

Webアプリ。

最初はスマホ利用を重視する。

将来的には、AIが生成した機能やUIをプレビューできるようにする。

---

## Deployment

GitHubを正本とする。

基本の流れ：

```text
AI / 人間
↓
GitHub
↓
Raspberry Pi
↓
Deploy
```

将来的には、

```text
AI
↓
PR作成
↓
プレビュー
↓
承認
↓
本番反映
```

を目指す。

---

## Safety

現実世界に影響する操作は慎重に扱う。

例：

* 家電操作
* 予定変更
* 通知送信
* コード変更
* デプロイ

自動実行レベル：

```text
Level 0: 提案だけ
Level 1: 確認して実行
Level 2: 安全なものだけ自動実行
Level 3: 完全自動
```

初期はLevel 0〜1を基本とする。

---

## 初期実装方針

最初に作るべきものは大きな機能ではなく、Jarvis Coreの骨格。

優先順：

1. docs整備
2. architecture定義
3. backend骨格
4. User / Permission
5. Tool Registry
6. Calendar Module
7. Web UI
8. Chat Operation
9. Travel Module移植

---

## 重要な考え

Jarvisは機能を直接知るのではなく、Toolを知る。

未来のAIが新機能を追加しやすいように、最初から増築前提で設計する。
