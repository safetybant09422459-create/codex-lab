# Jarvis Memory Architecture

## 目的

MemoryはJarvis Coreの必須基盤である。

MemoryがないJarvisは、現在の要求に応じてToolを呼べる便利な操作UIにはなれても、人格、
継続性、家族との関係性、過去を踏まえた判断文脈を育てられない。Memoryは会話機能の付属物や
単一Skillの追加機能ではなく、Jarvisが長期間同じ相手として振る舞うためのCore能力である。

本書は、Memoryに関する統治をJarvis Coreへ、保存や検索の実務をMemory Skillへ分け、Travel、
Photo、Calendar、Garden、Homeなどのドメインデータとの境界を定義する。

## 位置づけ

Memoryは「Coreが統治し、Memory Skillを通して利用する」基盤とする。

```text
Conversation / Tool result / Decision / Lesson
                    ↓
Jarvis Core: 記憶候補の判断、権限、Privacy、Retention
                    ↓
Memory Skill: 保存、検索、要約、更新、関連付け
                    ↓
Memory Store ── Evidence Ref ── Travel / Photo / Calendar / Garden / Home
                    ↓
Jarvis Core: 利用目的に必要なMemoryを選択
              ├ Planner
              └ Answer Generator
```

Coreの必須基盤であることと、Coreが保存方式や検索アルゴリズムを実装することは同義ではない。
CoreはMemoryの利用方針と安全境界を所有し、Memory Skillの公開Tool / API境界を利用する。
Memory SkillやMemory Storeが未実装でも、この責務分離を将来実装の前提とする。

## CoreとMemory Skillの責務

| 領域 | Jarvis Core | Memory Skill |
| --- | --- | --- |
| 記憶化 | 何を、なぜ、誰のMemory候補にするか判断する | 候補を検証可能なMemory表現として保存する |
| 想起 | 目的、User Context、現在の会話に必要なMemoryを決める | 条件に合うMemoryを検索し、順位付き候補を返す |
| AIへの受け渡し | PlannerとAnswer Generatorへ必要最小限のMemoryを渡す | 渡せる要約と参照情報を生成する |
| 更新 | 修正、統合、忘却の意図と許可を判断する | Memoryの更新、関連付け、削除または忘却処理を行う |
| Governance | 権限、Privacy、Retention、Forget、Auditの方針と適用を統治する | 方針を実施できる操作と記録を提供する |
| 実装詳細 | Storageや検索方式を知らない | 保存形式、索引、検索、要約方式を隠蔽する |

Memoryの読み取りと更新は、他のToolと同様に認証済みUser Contextを使い、Permission、
Confirmation、Auditの安全境界へ接続する。CoreやLLMがMemory Storeへ直接アクセスしてはならない。
Memory Skillは、各Skillが提供するEvidence参照をMemoryへ関連付けるが、参照先のドメインデータを
所有したり、Skill固有の意味判断を代行したりしない。

## MemoryとEvidence Skillの境界

Travel、Photo、Calendar、Garden、HomeなどはMemoryそのものではない。各Skillは自身のドメインで
正となるデータを所有し、Memoryから参照できるEvidenceを提供する。

| Skill | 所有する正 | Memoryからの参照例 |
| --- | --- | --- |
| Travel | Trip / Outing、Experience、旅行メモ | 家族旅行の思い出や次回判断の根拠 |
| Photo | Asset、Album、撮影時刻、Thumbnail | 思い出を裏付ける写真 |
| Calendar | Event、日時、参加者 | 約束や出来事の日時根拠 |
| Garden | 植物、作業、観察記録 | 学びや継続的な好みの根拠 |
| Home | 家の状態、操作結果、Automation | 家庭内の出来事や判断の根拠 |

MemoryはEvidenceのコピーを正として所有せず、意味、重要性、将来使える文脈と、参照可能な範囲で
Evidenceへのリンクを持つ。参照先が削除、非公開、訂正された場合に、Memoryを再評価または無効化
できる設計にする。参照先へ辿る際も、その時点のアクセス権を再検証する。

Travel文書で使う「Memory」や「Family Outing Memory Skill」は、Trip / Outing内の思い出文脈を
表すドメイン上の名称であり、Jarvis全体のMemory Skillを意味しない。Travel Memory Entityは
Travelが所有するEvidenceであり、必要なものだけがCoreの判断を経てJarvis Memoryになる。

## 会話記録とMemory候補

会話は、そのまま全件を長期Memoryとして保存しない。会話履歴は会話の再開や監査に必要な期間だけ
保持するデータであり、長期Memoryとは別に扱う。

重要な会話から、例えば次をMemory候補にできる。

* 家族との思い出
* 本人の継続的な好み
* 将来も使う判断とその理由
* 約束
* 印象的な出来事
* 学習と反省

保存時は会話全文を複製するのではなく、「誰についての情報か」「何が重要か」「どの場面で将来
使えるか」「根拠は何か」が分かる文脈へ整理する。必要な場合だけ、保持方針と権限の範囲内で
元会話、Travel、Photo、CalendarなどのEvidenceへ辿れる参照を残す。

会話からの抽出結果は確定Memoryではなく候補として扱う。高感度情報、共有範囲の拡大、本人以外に
関する推測は自動確定せず、明示確認やより厳しいPolicyを要求する。会話を削除した場合にEvidence
参照と派生Memoryをどう扱うかも、Retention / Forget方針で追跡可能にする。

## 人格形成と正確性

Jarvisの人格は口調だけではなく、次の蓄積から形成される。

* Vision
* Decision
* Lessons
* Preferences
* Important Memories

Memoryは、話し方、提案、判断、共感の背景になる。ただし、過去の情報で現在のユーザーを固定化
したり、Memoryだけを根拠に事実を作ったりしてはならない。

各Memoryでは少なくとも、確認された事実、本人の表明、Jarvisによる要約、推測を区別できるように
する。推測には根拠と不確実性を持たせ、事実として回答しない。矛盾するEvidenceやユーザーからの
修正があれば、訂正前の内容を無条件に使い続けない。

ユーザーは、自分に関するMemoryを確認、修正、削除、忘却できる。人格形成に使うMemoryを
ブラックボックス化せず、「なぜこの提案や話し方になったか」を説明できることを目指す。

## Privacy、所有者、公開範囲

Memoryは家族利用を前提に、少なくとも次を区別する。

* 誰についてのMemoryか
* 誰が作成または確認したか
* 誰が閲覧、利用、修正、共有、削除できるか
* `private`、`family`、`shared`などの公開範囲
* Retention期限とForget状態

`family`は家族全員への無条件公開を意味しない。本人、保護者、参加者などの関係と利用目的を含めて
認可する。子ども、健康、位置情報、家庭事情、家族写真、予定、在宅状態は高感度情報として扱い、
推測や関連付けを自動共有しない。外部AI Providerへ渡す場合も目的に必要な最小限にする。

Memoryの作成、修正、共有範囲変更、削除、忘却は更新系操作である。対象、変更内容、影響範囲を
示し、必要な確認と監査を通す。監査記録自体へMemory本文や高感度情報を過剰に複製しない。
Forgetは検索対象から外すだけで十分か、派生要約、索引、Evidence参照、バックアップまで削除するかを
Retention方針で定義し、実行結果を説明できるようにする。

## Chat CoreとConversation State

Conversation StateはMemoryではない。

Conversation Stateは、現在の会話で作業を継続するための短期的な状態である。例えば
`selected_trip`、`selected_photo`、現在のGoal、未確定候補を保持する。会話の終了や期限切れで
破棄でき、人格形成には直接使わない。

Memoryは、長期的な人格、思い出、判断、家族との継続性に使う。Chat CoreはConversation Stateを
そのままMemoryへ昇格させず、必要な内容だけをMemory候補としてCoreの記憶化判断へ渡す。応答時も、
現在の作業状態と長期Memoryを別の入力として扱い、出所と信頼度を混同しない。

この境界は[Chat Core v0.2 Foundation](chat_core.md)と
[Chat Core Skill Adapter Architecture](decisions/2026-06-chat-core-skill-adapter-architecture.md)の
Conversation State方針を維持する。

直近のuser／assistant発話は`ConversationWorkingContext`としてPlannerへ渡す。これは現在発話の
理解を助ける一時入力であり、Conversation StateにもMemoryにも保存しない。将来のMemory化では、
Working Context全体を暗黙に保存せず、Coreが選んだ必要最小限の内容だけを明示的なMemory候補として
Memory Skill境界へ渡す。

## 今回の非対象

本書では次を決定または実装しない。

* DB、schema、indexの追加
* Memory Skill、Tool、Repositoryの実装
* Chat挙動の変更
* 短期・中期・長期という三層記憶モデルの正式採用
* 自動記憶化の閾値や具体的なRetention期間の確定

## 将来のMemory Skill実装候補

実装時には、まずreadとユーザー確認を重視した小さな縦切りで次を検討する。

* Memory候補、確定Memory、Evidence参照、所有者、visibility、事実 / 推測区分の最小schema
* `memory.search`、`memory.get`などのread Tool
* `memory.create`、`memory.update`、`memory.forget`、Evidence関連付けなどのguarded write Tool
* Planner / Answer Generatorへ渡す目的別・権限適用済みContext契約
* ユーザーがMemoryと利用理由を確認、修正、削除できるWeb UI
* Retention、Forget、Evidence失効、派生要約を追跡するAudit設計
* Memory Skill Adapter / Resolverを登録し、Coreへ検索方式やSkill固有分岐を持ち込まない構成

これらは候補であり、現時点の実装済み機能を表さない。

## 既存設計との接続

* [Jarvis Core Architecture](architecture.md): Core、Skill、Runtime、Memoryの上位境界
* [Jarvis Vision](vision.md): 家族と長期間付き合うJarvisと人格の考え方
* [Decision Log](decision_log.md): AI人格の記憶とSkill DBを分離する決定
* [Travel Skill](travel.md): おでかけ文脈とTravel Memory Entity
* [Travel Data Model](travel_data_model.md): Travelが所有するEvidenceのモデル
* [Jarvis Principles and Constitution](../chatgpt_docs/01_principles_and_constitution.md): Privacy、Skill Independence、Human in Control

## Jarvis Principle Check

1. Web UIから利用できるか
   * 将来、Memoryの一覧、根拠、公開範囲、修正、Forgetを確認する入口を提供できる。今回はdocsのみである。
2. API / Toolとして利用できるか
   * Memory Skillのread / guarded write Tool境界として利用できる設計である。
3. 将来MCP Tool化できるか
   * できる。readから始め、writeは認証、Permission、Confirmation、Auditを必須にする。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。Coreが利用判断を行い、Memory Skillの公開境界を通す。
5. UI依存のロジックになっていないか
   * なっていない。Memoryの判断、保存、検索、PrivacyはCore / Tool / Skill境界に置く。
6. 読み取り系か更新系か
   * Memory利用全体はmixed。検索と取得はread、保存、修正、関連付け、Forgetはwriteである。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。人格への影響、家族間の情報漏えい、推測の事実化、過剰保持、外部送信、削除漏れを防ぐ必要がある。
