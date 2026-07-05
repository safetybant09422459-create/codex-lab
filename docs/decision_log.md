# Decision Log

## Decision 0001

### テーマ

このプロジェクトの中心は何か？

### 候補

* 旅行アプリ
* 家族ポータル
* AIエージェント

### 決定

AIエージェント

### 理由

旅行、家電、予定、写真はすべてAIが利用するToolである。

主役は機能ではなくAI。

---

## Decision 0002

### テーマ

旅行アプリをどう扱うか？

### 決定

旅行アプリはJarvisの最初のモジュールとする。

### 理由

旅行アプリは完成形ではなく、Jarvisを構成する一機能である。

---

## Decision 0003

### テーマ

AIの成長方針

### 決定

人間承認型から開始する

### 理由

現在のAIはまだ完全自律には早い。

まずは

AI
↓
提案
↓
人間承認

を採用する。

将来的には自律度を高める。

---

## Decision 0004

### テーマ

記憶の持ち方

### 決定

ハイブリッド方式

### 理由

AI人格の記憶と各モジュールのデータを分離する。

例

* jarvis.db
* travel.db
* garden.db

---

## Decision 0005

### テーマ

将来の利用者

### 決定

家族全員

### 理由

ただし権限管理を導入する。

プライバシーを尊重する。

例

* private
* busy
* family
* shared

---

## Decision 0006

### テーマ

Jarvis vNextの意味判断と実行安全性をどこへ置くか？

### 決定

意味判断を単一のLLM Agent Loopへ集約し、PythonはAgent Host、Action Gateway、Domain Capabilityの
決定的処理だけを担う。Activation RAGはRecall Index、EvidenceはGrounded Factへ整理する。

### 詳細

[Jarvis vNext Single Agent Loop Architecture](decisions/2026-07-vnext-single-agent-loop-architecture.md)を参照する。

---

## Decision 0007

### テーマ

SkillとProviderの責務をどう分けるか？

### 決定

Skillはユーザーから見える能力・機能単位、Domain ProviderはCoreが利用する能力提供境界とする。
ProviderはSkillとは別の頭脳や必須microserviceではなく、MCP、REST API、Local Serviceで交換可能な契約面である。

### 詳細

[Domain Provider Responsibility Boundary](decisions/2026-07-domain-provider-boundary.md)を参照する。
