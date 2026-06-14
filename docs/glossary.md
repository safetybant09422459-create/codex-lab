# Glossary

## Jarvis

家庭用AIエージェント。

このプロジェクトの主役。

旅行、予定、家電、写真などの機能を利用する。

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
