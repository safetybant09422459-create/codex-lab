# Jarvis Runtime

## 目的

Jarvis Runtimeは、AI Agentが選択したToolを安全に実行するための実行層である。

Jarvisは機能を直接実行しない。

必ずRuntimeを通して、

* Tool Registry
* Permission Check
* Confirmation
* Execution
* Audit Log

を扱う。

---

## Runtimeの役割

RuntimeはJarvis Coreの中で、Tool実行の責任を持つ。

主な役割：

* AI AgentからTool実行リクエストを受け取る
* Tool RegistryからTool定義を確認する
* ユーザー権限を確認する
* リスクレベルを判定する
* 必要なら人間に確認する
* Toolを実行する
* 実行結果をAI Agentへ返す
* 実行履歴をAudit Logへ記録する

Runtimeは便利さだけではなく、信頼を守るための境界である。

---

## Tool Registry

Tool RegistryはJarvisが利用可能なTool一覧を管理する。

Toolは以下の情報を持つ。

* name
* description
* input schema
* output schema
* required permission
* risk level
* module name
* enabled / disabled
* confirmation required

例：

```text
calendar.create_event
travel.add_spot
appliance.turn_off
notification.send
code.create_pr
```

AI AgentはToolを自由に呼び出せるわけではない。

RuntimeはTool Registryを見て、そのToolが存在するか、有効か、現在のユーザーに許可されているかを確認する。

---

## Permission Check

Permission Checkは、誰が何を実行できるかを確認する仕組みである。

確認するもの：

* user
* role
* target data
* required permission
* privacy level
* risk level

ユーザー権限の例：

```text
Owner
Adult
Child
Guest
```

プライバシーレベルの例：

```text
private: 本人だけ
busy: 詳細を隠して予定ありだけ表示
family: 家族に表示
shared: 全員に表示
```

コード変更、家電操作、デプロイなど現実世界に影響する操作は、強い権限を必要とする。

権限が不足している場合、RuntimeはToolを実行しない。

---

## Audit Log

Audit Logは、Jarvisが何を判断し、何を実行したかを記録する。

記録するもの：

* requested by
* tool name
* input
* permission result
* risk level
* confirmation result
* execution result
* error
* timestamp
* reason

Audit Logの目的：

* あとから説明できること
* 失敗から学べること
* 家族利用で信頼を保つこと
* 自動化の範囲を安全に広げること

Jarvisは実行したことだけでなく、実行しなかった理由も記録する。

---

## 実行フロー

基本フロー：

```text
User
↓
AI Agent
↓
Tool Selection
↓
Runtime
↓
Tool Registry
↓
Permission Check
↓
Risk Check
↓
Confirmation
↓
Tool Execution
↓
Audit Log
↓
Result
↓
AI Agent
↓
User
```

Runtimeは、Tool実行前と実行後の両方で記録を残す。

実行前には、なぜそのToolを実行しようとしたかを記録する。

実行後には、実際に何が起きたかを記録する。

---

## リスクレベル

Toolにはリスクレベルを持たせる。

初期案：

```text
Risk 0: 読み取りのみ
Risk 1: 個人データを含む読み取り
Risk 2: 変更を伴うが取り消しやすい操作
Risk 3: 通知、共有、外部送信
Risk 4: 家電、コード変更、デプロイなど強い影響がある操作
```

例：

```text
calendar.list_today_events: Risk 1
calendar.create_event: Risk 2
notification.send: Risk 3
appliance.turn_off: Risk 4
code.create_pr: Risk 4
```

初期はRisk 0以外を慎重に扱う。

Trust Before Automationを優先し、自動化より確認を重視する。

---

## 確認フロー

Jarvisは最初から完全自動で動かない。

基本は、

```text
提案
↓
確認
↓
実行
```

とする。

確認が必要な例：

* 予定を作成する
* 予定を変更する
* 家電を操作する
* 通知を送る
* 写真や予定を家族に共有する
* コードを変更する
* PRを作成する
* デプロイする

確認時にJarvisが伝えること：

* 何を実行するか
* なぜ実行するか
* どのToolを使うか
* どのデータに影響するか
* リスクレベル
* 取り消し可能か

ユーザーが承認した場合のみ、RuntimeはToolを実行する。

ユーザーが拒否した場合、Runtimeは実行せず、理由をAudit Logへ記録する。

---

## 自動化レベル

Runtimeは将来的に自動化レベルを扱う。

```text
Level 0: 提案だけ
Level 1: 確認して実行
Level 2: 安全なものだけ自動実行
Level 3: 完全自動
```

初期はLevel 0からLevel 1を基本とする。

自動化レベルは、Tool単位、ユーザー単位、Module単位で変えられるようにする。

---

## 重要な考え

RuntimeはAIの自由を制限するためだけの仕組みではない。

AIが家族から信頼され、将来より多くのことを任されるための土台である。

Jarvisは、

* 何ができるか
* なぜ実行したか
* 誰が許可したか
* 何が起きたか

を説明できる必要がある。

Runtimeはその説明責任を支える。
