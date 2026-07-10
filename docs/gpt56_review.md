# Catalog Principle / Guardrail 設計更新

変更点

- [Catalog Principle / Guardrail](decisions/2026-07-catalog-principle.md)を強化しました。
- Operation / Capability / Dashboard Catalogの正本を分離し、LLM context、Status Provider、API、MCP、UIは派生viewと定義しました。
- 宣言を装ったrouting、ranking、固定回答、UI選択を検出するレビューGuardrailを追加しました。
- Architecture、README、AGENTS.md、Principles、Provider Contractへの導線は既に整備済みのため、重複編集していません。

Catalogの違い

- Operation: LLMがProvider Operationを選択するための実行契約。
- Capability: ユーザー向けの自然な能力説明。Operation一覧ではない。
- Dashboard: UIが描画可能な候補metadata。現在の表示選択はしない。

Python頭脳再発防止

- keyword、example、tag、score、`use_when`を発話routingに使わない。
- permission / visibility filterは安全な除外だけを行い、意味的rankingをしない。
- Jarvis Status Provider、UI、MCP adapterは決定的な投影・描画だけを行う。
- Catalog entryを認可、Evidence、実装状態、Runtime gateの代替にしない。

MCPとの関係

- Operation CatalogをMCP Tool metadataへ投影可能な内部契約としました。
- MCPはprotocol / transportであり、Tool選択はLLM/Core、実行可否はRuntimeが担います。

検証結果

- `git diff --check`: 成功
- Markdownリンク実体確認: 成功
- 変更はDecision文書1件、25行追加のみ
- コード変更・commit・push: なし

未解決

- なし

次の候補

- 実装してよい: 3 Catalogのschema/version、正本からの決定的投影、visibility filter、validation、MCP metadata投影。
- まだ危険: keyword router、Catalog ranking、Channel/Provider別planner、Python fallback回答、固定カード優先順位、UI内の表示選択。

Jarvis Principle Check

1. Web UI: 選択済みDashboard候補だけを描画する境界です。
2. API / Tool: Operation Catalogを実行契約として利用できます。
3. MCP: metadataへ投影可能ですが判断層にはしません。
4. Jarvis Core: filter済みCatalogからLLM/Coreが選択します。
5. UI依存: 表示判断をUIへ置きません。
6. read/write: Catalogはread、実行安全性は各OperationとRuntimeが管理します。
7. 副作用・権限・プライバシー: Catalogを認可の代替にせず、permission / visibility filterとRuntime gateを維持します。
