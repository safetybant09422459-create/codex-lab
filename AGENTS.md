# Jarvis AI Agent Guide

この文書は、人への引き継ぎ資料ではなく、ChatGPT、Codex、Claude CodeなどのAI Coding Agentが、このリポジトリを読んで安全に自走するための入口である。設計の正本を複製せず、読む順序、判断規則、作業手順だけを定める。

## 1. Project Identity

Jarvisは、家族の記憶、予定、写真、旅行、家、庭、開発状態を扱う家庭用AIエージェントである。長期像は、Web、Chat、Voice、Notification、MCP、将来のRobotが同じJarvis CoreとSkill / Tool境界を利用することにある。詳細は `docs/vision.md` と `docs/architecture.md` を参照する。

- 中心は `Jarvis / Jarvis Core` であり、個別アプリではない。
- Jarvis screenはSkillを統合する入口。Homeはトップ画面の別名ではなく、家電や在宅状態を扱う独立した高リスクSkillである。
- Travelは最初のSkillかつActivation RAGのProvider / PoCであり、Coreの完成形ではない。
- Developer Skillは、リポジトリ変更、Codex実行、service操作を扱う管理者向けの高リスクSkill / 将来のMCP候補である。一般Chatの能力と混ぜない。
- LLMが意味判断、Capability選択、Evidence評価、回答を担う。PythonはRuntime、Validation、Permission、Confirmation、Audit、Repository、決定的変換を担う。

## 2. Authority and Core Principles

判断が競合した場合は、現在のユーザー指示と実行環境の安全制約、`docs/principles.md`、採用済みDecision、Architecture、実装とテスト、補助・引き継ぎ文書の順に優先する。`chatgpt_docs/` はAI共有用の要約であり、通常docsと現行コードを置き換えない。

原則の正本は `docs/principles.md`、責務境界は `docs/architecture.md`、Runtime規則は `docs/runtime.md`、採用理由は `docs/decision_log.md` と `docs/decisions/` を参照する。作業中は少なくとも次を守る。

- AI / LLM First: Pythonに自然言語キーワード分岐や固定回答を増やして「第二の頭脳」を作らない。
- Conversation Quality / Python Brain Regression Guard: 会話品質はContext、Observation、Provider契約、Catalog説明、Memory、promptを改善して上げる。テストを通すためのPython意図判定、話題判定、Provider / Operation選択、Clarification、fallback回答を追加しない。レビューでは「LLMへの材料改善か、Python判断の追加か」を必ず確認する。Improvement Target Principleの詳細は `docs/decisions/2026-07-conversation-quality-python-brain-regression-guard.md`。
- Observation Guardrail: Observationは観測された事実だけを持ち、解釈、意図・話題、次Action、推薦、回答、Provider / Operation選択、UIカード判断を持たない。レビューではfield名だけでなく生成過程がraw resultから決定的に再現できるかを確認する。詳細は `docs/decisions/2026-07-observation-guardrail.md`。
- Runtime / Tool First: 機能を明確な入出力を持つToolとして設計し、writeはValidation、Permission、Confirmation、Auditを迂回しない。
- Repository / DB is Source of Truth: Domain EntityはRepositoryから再取得する。コメント、README、Skill metadata、検索索引だけで実装状態を確定しない。
- RAG is not Source of Truth: Activation RAGは未検証候補を返すread-only補助であり、Evidence、権限、Entity確定、実行許可ではない。
- Thin Core: Provider固有・Skill固有の語彙、型、ranking、外部API詳細をCoreへ持ち込まない。
- Skill Independence: Skillは標準レイヤーに従い、可能な限り単体でも動作する。詳細は `docs/skill_standard_architecture.md`。
- Provider Independence: AI、検索、外部サービスのProvider固有処理はAdapter境界へ閉じ込める。
- Domain Provider Boundary: Skillはユーザーから見える能力単位、Domain ProviderはCore向けの能力提供境界とする。ProviderはCRUD、検索、Repository、外部API、決定的ドメイン処理を担うが、意図解釈、Provider / Operation選択、Clarification、会話、最終回答を担わない。
- Catalog is declarative, not decision logic: Operation、Capability、Dashboard Catalogを分離し、発話routing、Provider / Operation選択、固定回答、表示優先順位を入れない。Pythonはschema validationとprincipal / permission / visibilityの決定的filterに限定する。詳細は `docs/decisions/2026-07-catalog-principle.md`。
- UI is an entry point: ドメイン判断や重要な副作用をfrontendへ閉じ込めない。Web UI、API / Tool、将来MCPから同じ境界を使う。
- Privacy First / Trust Before Automation: 家族情報、写真、予定、位置、在宅、開発操作は最小権限、確認、監査、可視性を設計する。自動化より信頼を優先する。
- Safari First: frontend変更はiPhone / Safari互換と、画面ごとの障害分離を確認する。

## 3. Reading Order

全ファイルを無差別に読むのではなく、次の順で必要範囲を深掘りする。

1. `AGENTS.md`、ユーザー指示、`git status --short --branch`、`git diff`。作業境界と既存差分を確定する。
2. `docs/principles.md`、`README.md`。不変原則、起動方法、現在の実装概要を得る。
3. `chatgpt_docs/99_handoff_summary.md` と `chatgpt_docs/90_current_status.md`。現在Phaseと既知の未実装を把握し、必ずコードと照合する。
4. `docs/architecture.md`、`docs/runtime.md`、`docs/skill_standard_architecture.md`、`docs/decisions/2026-07-turn-contract-single-agent-loop.md`、`docs/decisions/2026-07-llm-contract.md`、`docs/decisions/2026-07-domain-provider-boundary.md`、`docs/decisions/2026-07-catalog-principle.md`、関連する `docs/decisions/`。責務と採用済み判断を確認する。
5. 対象Skillの `skills/<skill>/skill.json`、`tools/<skill>/*.json`、関連docs。metadataと契約を確認する。
6. Executor、Repository、Storage / Adapter、API、frontend、testsの順に関連コードを追う。Toolの実装有無はJSONのstatusだけで決めない。
7. Chat / RAG作業では `docs/chat_core.md`、`docs/context_assembly.md`、`docs/activation_rag.md`、`docs/knowledge_enrichment.md` を追加で読む。
8. 実装直前に対象ファイルの履歴と最新diffを確認し、実装後に全diffを再読する。

## 4. AI Workflow

### Explore

- 見る: Git状態、関連docs / Decision、Skill / Tool JSON、呼び出し元と呼び出し先、tests。
- 判断: 依頼範囲、正本、既存差分の所有者、read/write、リスク、現在実装と設計案の差。
- 実行: `rg` で関連箇所を横断し、UIからRepositoryまでの経路を追う。秘密情報やDB実体の内容は不用意に表示しない。

### Reason

- 見る: Constitutionとの整合、Runtime境界、類似Skillの実装パターン、失敗時の挙動。
- 判断: LLMと決定的コードの責務、CoreとSkillの境界、互換性、権限・確認・監査・プライバシー。
- Observation変更時の判断: factsが決定的な観測結果か、意味解釈・次Action・回答・表示判断をProvider / Runtimeへ移していないか、最小開示・visibility・freshness・limitations・provenanceを満たすか。
- 実行: 仮説と根拠を短く整理する。docsとコードが違う場合はコードとテストを現状として扱い、差異を報告する。

### Plan

- 見る: 変更候補、関連テスト、検証コマンド、migration / API / Tool契約への影響。
- 判断: 最小の変更集合、再利用する既存パターン、ロールバック可能性、docs / Decision更新の要否。
- 実行: 複数工程なら検証可能な単位に分ける。未確認migration、大量削除、外部副作用は計画段階で停止条件にする。

### Implement

- 見る: 直前の対象コードとユーザー差分。
- 判断: 依頼に必要な変更だけか、既存API・Tool・UI互換を壊さないか。
- 実行: 最小差分で既存命名・層・エラー形式を流用する。無関係な整形やリファクタリングを混ぜない。秘密、`.env`、DB実体、ログを追加しない。

### Verify

- 見る: 変更に近いテストから全体テスト、lint / typecheck設定、起動経路、diff whitespace。
- 判断: 成功条件を満たすか、未検証部分が残るか、失敗が変更由来か環境由来か。
- 実行: 利用可能な範囲で対象test、全test、lint、typecheck、起動 / API確認、`git diff --check` を行う。Python検証はREADMEどおり原則 `./.venv/bin/python` を使う。

### Review

- 見る: `git diff --stat`、全 `git diff`、`git status --short`、新規ファイル、secret / 大容量 / DB混入。
- 判断: 意図しない変更、境界違反、削除過多、テスト不足、説明と実装の不一致がないか。
- 実行: Reviewerの立場で自己レビューし、必要なら修正して再検証する。

### Report

- 見る: 最終差分、検証結果、未解決事項。
- 判断: 完了か、何が安全に未完か、次に価値がある作業は何か。
- 実行: 「変更点」「検証結果」「未解決」「次の候補」だけを簡潔に報告する。変更時は末尾にJarvis Principle Checkを付ける。

## 5. Development Rules

- 変更は依頼を満たす最小限にする。既存設計、同じ層の実装パターン、公開契約を優先する。
- 対象だけでなく、呼び出し元、呼び出し先、Tool JSON、Runtime gate、tests、UI入口を確認する。
- コメントや文書より実行コードとテストを現状の証拠として信用する。ただし採用済み原則から逸脱する実装を無批判に複製しない。
- 設計より実装を優先した場合は、互換性、段階移行、現行制約など具体的理由と残課題を報告する。
- 設計判断を変える場合はDecision、再発防止の学びはLessons、今やらない案はIdea Backlogへ置く。単なる実装詳細を重複記録しない。
- DB migration、Tool契約変更、権限変更、破壊的操作は通常変更から分離し、明示的にレビューする。
- `/mnt/nas/projects/project` は別プロジェクトであり変更しない。作業環境の上位制約がより狭い場合は必ずそちらを守る。

## 6. Verification Rules

変更リスクに比例して、可能な限り次を実施する。

1. 変更箇所に最も近いtest
2. `./.venv/bin/python -m unittest discover -s tests`
3. リポジトリに設定済みのlintとtypecheck（未設定なら未実施と明記し、勝手に導入しない）
4. README記載の起動確認または関連API smoke test
5. `git diff --check`
6. 全diff、status、秘密情報、生成物、DB、大容量ファイルの自己レビュー

検証失敗時は原因を変えずに同じ操作を反復しない。仮説を更新して最大3回まで自己修正・再検証し、同じ本質的失敗が続く、または安全な修正根拠がない場合は停止して、実行コマンド、エラー、試した修正、残る仮説を報告する。

## 7. Commit / Push Policy

commit / pushの可否は、現在のユーザー指示、実行環境、Developer Toolの安全制約を最優先する。禁止されている場合は実施せず、毎回確認もしない。

ユーザーが「自走」「最後まで」「完了まで」「pushまで」など、公開まで進める意図を明示した場合は、それをcommit / pushの事前承認として扱ってよい。次をすべて満たしたときだけ、追加質問なしで意図的なcommitを作り、pushまで依頼されていれば現在branchへpushできる。

- 必要なテストが成功した。
- `git diff --check` が成功し、全diffを自己レビューした。
- secret、`.env`、DB実体、ログ、生成物、大容量ファイルを含まない。
- ユーザー由来と思われる未コミット変更や意図しない変更を含まない。
- migration、削除、権限、外部副作用が確認済みである。
- commit対象とメッセージを説明でき、push先branch / remoteが明確である。

次の場合はcommit / pushせず停止して報告する: テスト失敗、未確認migration、大量または予期しない削除、秘密情報、`.env`、DB実体、大容量ファイル、ユーザー作業と思われる未コミット変更、branch / remote不明、force pushが必要。明示依頼のないforce push、履歴改変、破壊的Git操作は行わない。

現行Jarvis Dev v0.3は安全指示によりCodex CLIのcommit / pushを禁止し、Developer UIから人間が操作する構成である。その実行では本節の自動化条件より禁止指示を優先する。

## 8. Jarvis-specific Continuity

- AGENTS.mdを常設入口とし、handoff promptへ不変原則を毎回コピーしない。現在地だけを `chatgpt_docs/99_handoff_summary.md` に保つ。
- Developer Skillは、将来 `Explore -> Plan -> Verify -> Review -> Report` の構造化結果、変更ファイル、検証結果、risk、commit readinessを返す契約へ育てる。`developer.run_codex` とservice操作はhigh riskのままConfirmation / Auditを必須にする。
- Activation RAGにはDomain Entityの候補だけを載せる。AGENTS.md、Decision、Tool schema、承認済み利用例を扱う場合は、正本を置き換えない別のDeveloper Context / Capability Usage索引として設計する。
- AIが自走しやすいよう、将来はCIにdocs link check、Tool JSON schema検証、Executorとの実装状態整合、secret scan、`git diff --check`、testを追加する。
- 機械可読な `current_phase`、Capability Catalog、検証コマンドを単一のmanifestへ集約する案を検討する。導入まではREADME、current status、コードの三者を照合する。
- Decisionには「何を採用したか」と再検討条件、Toolには入出力・risk・confirmation・audit、testsには契約例を残す。会話ログを設計の正本にしない。

## 9. Completion Report Template

```text
変更点
- ...

検証結果
- ...

未解決
- なし / ...

次の候補
- なし / ...
```

Jarvis Principle Checkは、Web UI、API / Tool、将来MCP、Jarvis Core、UI依存、read/write、副作用・権限・プライバシーの7点を各1行で評価する。
