# Jarvis Principles and Constitution

更新日: 2026-06-27

## 目的

Jarvisは、便利な単機能アプリではなく、家族と長期間付き合うPersonal AI Systemである。機能追加の速さより、信頼、説明可能性、交換可能性、プライバシーを優先する。

## 憲法

### AI First, Human in Control

ユーザーは自然文で目的を伝え、Jarvisが必要なSkill / Toolを選ぶ。ただしAIは権限主体ではない。更新、共有、削除、外部作用は人間の権限と確認に従う。

### Tool First

重要な能力はUI内部の処理ではなく、入力・出力・risk・confirmation・auditを持つToolとして定義する。同じ能力をWeb、Chat、将来のVoice / MCPから再利用できるようにする。

### Runtimeを迂回しない

ToolはValidation、Permission、Confirmation、Auditを通る。UIやLLMがRepository、DB、外部APIへ直接書き込まない。

### Web UI Required

AIだけに依存せず、人間が一覧、詳細、変更内容、確認、履歴、エラーを見られるWeb UIを持つ。Chatは新しい入口であり、既存Skill UIを置き換えない。

### Provider Independent

OpenAI、Immich、Google等のprovider固有処理はAdapterへ閉じ込める。Jarvis Core、Skill、Tool schemaをproviderの都合に結合しない。

### Privacy First

家族写真、子どもの情報、位置、予定、家の状態、会話は高い慎重さで扱う。外部送信は目的に必要な最小限とし、secretをfrontend、model prompt、Tool result、auditへ出さない。

### Trust Before Automation

初期段階はreadと提案を中心にする。writeは対象、変更前、変更後、副作用を見せて確認する。自動化は、利用実績、監査、取消・復旧手段が整ってから段階的に増やす。

### Explainability and Auditability

どのToolを、誰の権限で、どの引数で、なぜ選び、成功・失敗・blockのどれになったか追跡できるようにする。自然文の説明と機械的なauditを分けて持つ。

### Skill Independence

Skillは責務とデータ所有境界を明確にする。Travelは旅行文脈、Photoは写真Assetと検索、Calendarは予定、Homeは家の操作を担当する。Skill間は公開Tool / Repository境界で連携する。

### Coreは薄く、ドメインはSkillへ

Jarvis Coreは意図理解、Tool選択、会話context、応答構成を担当する。Travel固有の期間計算、Photo Link、Experience更新ルールをCoreやChat UIへ移さない。

### Ideas and Decisions Are Assets

設計案、決定、未解決事項、学びをdocsへ残す。ただし将来案と実装済みを明示し、古い資料が現在の能力に見えないようにする。

## 家族利用の原則

- user / family / guest / adminを実認証へ結び付ける
- 家族だから全データ・全操作を自動許可しない
- 子どもの写真や位置を外部公開しない
- 推定Photo Linkを確定・共有扱いしない
- 会話履歴の保存有無、保持期間、削除を選べるようにする
- 高リスク操作は失敗時に安全側へ倒す

## 開発前チェック

1. Web UIから理解・操作できるか
2. API / Toolとして再利用できるか
3. 将来MCP Tool化できる境界か
4. Jarvis CoreからRuntime経由で呼べるか
5. UI依存のドメインロジックがないか
6. read / write / mixedのどれか
7. 副作用、権限、確認、監査、プライバシーを定義したか

## Chat v0.1への適用

ChatはToolの新しい実行入口である。modelへ自由な実行権限を与えない。server-side allowlist、構造化引数、Runtime、pending action型のwrite確認、上限設定、Auditを必須とする。Chat回答はTool結果を根拠にし、確認できない写真内容や存在しないIDを作らない。
