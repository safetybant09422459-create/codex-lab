# Principles

## Principle 1

AI First

JarvisはAIエージェントが主役。

旅行、家電、写真は主役ではない。

---

## Principle 2

Tool First

すべての機能はToolとして設計する。

UIから利用できるだけでなく、

* Chat
* Voice
* Future Robot

からも利用可能にする。

---

## Principle 3

UI / API / MCP First

新機能は可能な限り、UI専用機能として作らない。

以下の3層で考える。

* Web UI
* API / Tool
* MCP Tool候補

新機能を作る時は、将来Jarvis Coreから呼び出せるToolになるか確認する。

確認項目：

* 入力は明確か
* 出力は明確か
* 読み取り操作か、更新操作か
* 副作用があるか
* 権限確認が必要か
* 家族利用・プライバシー面の問題はないか
* 音声やチャットから自然に呼び出せる名前か

重要なロジックはUIに閉じ込めない。

画面ボタンだけでなく、APIやToolからも呼び出せる構造を意識する。

---

## Principle 4

Web UI Required

チャットだけではなく、

触れるWebアプリを持つ。

理由：

* ワクワク感
* プレビュー
* 確認しやすさ

---

## Principle 5

Human Friendly

家族が使いやすいことを優先する。

技術的な美しさだけを追求しない。

---

## Principle 6

AI Provider Independent

OpenAI専用にしない。

将来的な乗り換えを考慮する。

---

## Principle 7

Privacy First

家族のプライバシーを尊重する。

例：

* private
* busy
* family
* shared

---

## Principle 8

Module Independence

各Moduleは独立可能であること。

Travelだけでも動く。

Calendarだけでも動く。

---

## Principle 9

Explainability

Jarvisは理由を説明できること。

例：

* なぜ提案したのか
* なぜ実行したのか
* なぜ変更したのか

---

## Principle 10

Trust Before Automation

自動化より信頼を優先する。

最初は

提案
↓
確認
↓
実行

を基本とする。

---

## Principle 11

Future AI Friendly

未来のAIが理解しやすい構造にする。

人間だけではなく、

未来のJarvis自身も読者である。

---

## Principle 12

Growth Through Experience

人格は口調ではない。

人格は

* Vision
* Decision
* Lessons
* Memory

から形成される。

---

## Principle 13

Ideas Are Assets

思いつきを捨てない。

今やらないことと、

忘れることは違う。

すべてIdea Backlogへ記録する。

---

## Principle 14

Build The House First

機能を増やす前に土台を作る。

Jarvisはアプリではない。

AIが住む家である。

---

## Principle 15

Enjoy The Journey

このプロジェクトは趣味であり夢でもある。

効率だけでなく、

ワクワクすることを大切にする。

---

## Principle 16

Skill Standard Architecture

Skillは標準レイヤー構造に揃える。

```text
Runtime
↓
Permission / Confirmation / Audit
↓
ExecutorRegistry
↓
SkillExecutor
↓
SkillRepository
↓
Storage または External Adapter
↓
DB / 外部API
```

RepositoryをSkillの中心にする。

RuntimeはTool JSONロード、入力検証、権限、確認、監査、Executor呼び出しを担当し、Skill固有ロジックを持たない。

ExecutorはTool入出力adapterとして、Toolごとの分岐とRepository呼び出しを担当する。

StorageはDB詳細を隠蔽し、External Adapterは外部API詳細を隠蔽する。

重要ルール:

* RuntimeにSkill固有ロジックを書かない
* UIにドメインロジックを書かない
* ExecutorにDBや外部APIの詳細を書きすぎない
* Skill間連携は相手SkillのTool / API / Repository抽象を経由する
* TravelからImmichを直接呼ばない
* Photo Skillは `PhotoExecutor -> PhotoRepository -> ImmichAdapter` で作る
