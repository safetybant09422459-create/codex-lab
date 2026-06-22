# Glossary

## Jarvis

家庭用AIエージェント。

このプロジェクトの主役。

旅行、予定、家電、写真などの機能を利用する。

UI上では、AIがその時に合った情報を統合して表示するトップ入口の名前としても扱う。

`Home` とは呼ばない。

---

## Jarvis Core

Jarvisの中核。

以下を管理する。

* AI
* Users
* Permissions
* Memory
* Tool Registry
* Notifications

Jarvis Coreは、Travel、Photo、Garden、Calendar、Home、DeveloperなどのSkill / Toolを調停する。

UI画面そのものではなく、Jarvis画面が何を表示すべきかを判断するための中核である。

---

## Jarvis screen

UI上のトップ画面。

単なるダッシュボードではなく、Jarvis Coreが複数Skillの情報を統合し、今見せるべきものを表示する入口。

現時点では「喋らないJarvis」として扱い、将来的な双方向会話、音声、通知、自律提案の土台にする。

---

## Home Skill

Home Control / Home Automation系Skill。

Jarvis本人やトップ画面ではない。

扱うもの：

* 家電
* 家の状態
* 消し忘れ
* 在宅
* 旅行モード

現実世界への作用、在宅情報、生活パターンを扱うため、高リスクSkill候補として扱う。

---

## Tool

AIが利用する機能。

例：

* travel.create_trip
* calendar.create_event
* appliance.turn_off

Jarvisは機能を直接知るのではなく、Toolを知る。

---

## Module

Tool群をまとめた機能単位。

例：

* Travel Module
* Calendar Module
* Appliance Module

Moduleは独立して動作可能であることを目指す。

---

## Memory

Jarvisの人格を形成する情報。

単なる会話履歴ではない。

含むもの：

* Vision
* Decision
* Lessons
* Preferences
* Important Events

---

## Vision

Jarvisが目指す未来。

長期目標。

変更されることもある。

---

## Decision

重要な設計判断。

なぜその判断をしたかを記録する。

---

## Lesson

失敗や経験から得た学び。

人格形成に利用する。

---

## User

Jarvisを利用する人。

例：

* パパ
* ママ
* 長女
* 次女

---

## Permission

操作可能範囲。

例：

* Owner
* Adult
* Child
* Guest

---

## AI Provider

AIモデル提供元。

例：

* OpenAI
* Claude
* Gemini
* Local AI

Jarvisは特定Providerに依存しない。

---

## Idea Backlog

実装未定のアイデア保管庫。

思いついたら記録する。

実装順は問わない。

---

## Decision Log

重要な意思決定履歴。

未来の人間やAIへの説明責任を果たす。

---

## Lessons Learned

失敗と学びの記録。

Jarvisの人格形成に利用する。

---

## Trust

ユーザーがJarvisを信頼するための考え方。

透明性
説明責任
履歴管理

を重視する。
