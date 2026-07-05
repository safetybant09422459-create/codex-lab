# Handoff Summary

更新日: 2026-07-05

## 次回ChatGPTが最初に理解すること

Jarvisの開発フェーズは変わった。Travel Chat互換は削除済みであり、Basic ChatはToolなしへダウングレードした。
今後の中心は単一LLM Agent Loop、Domain Provider Contract、Travel Provider Operationである。

## 完了したこと

* Travel Chat Router、Planner、Plan Executor、Entity Resolver、Answer Generator、Response Composerを削除した。
* `/api/chat`はToolなしBasic Chatのみを返す。
* Runtime経由でValidation、Permission、Confirmation、Audit、Tool実行を行う。
* Domain Provider / OperationContext最小契約とTravelProviderを追加した。
* PythonによるTravel自然言語判断・固定回答生成を物理削除した。
* Activation RAGの共通Document、in-memory lexical index、Travel Provider PoC、Chatへのread-only候補注入を
  実装した。

現在の要約:

```text
Chat Channel -> ToolなしBasic Chat（暫定）
Runtime -> TravelExecutor adapter -> TravelProvider -> TravelRepository
```

## 変えてはいけない設計思想

1. **LLM First**: LLMが意味判断と回答を担う。PythonはRuntime、Permission、Confirmation、Audit、
   Validation、Repository等の実行基盤である。
2. **Repository is the Source of Truth**: Activation RAGはDBを思い出す索引であり、DBの代替ではない。
3. **候補はEvidenceではない**: RAG結果からEntity、回答、Tool実行を確定せず、Repositoryで再取得する。
4. **TravelはPoC**: Travel RAGを作らない。TravelはJarvis Activation RAGの最初のProviderである。
5. **CoreはProvider中立**: Travel固有の型、語彙、alias、rankingをCoreへ入れない。
6. **Enrichmentは検索だけを育てる**: 会話、失敗検索、ユーザー修正からalias、tag、relation、検索Document
   候補を作るが、本体DBは更新しない。
7. **ActionとSearchを分ける**: 「テレビつけて」のActionと、「神戸で何した？」「写真ある？」の
   Memory / Domain Searchは別設計である。

## 次に作る順番

1. Activation RAG Core
2. Travel Provider改善
3. Entity Resolution
4. Knowledge Enrichment
5. Memory Provider
6. Photo Provider
7. Calendar Provider
8. Capability Usage RAG検討

Capability Usage RAGは、Skill / Toolの承認済み利用例を検索してCapability選択を補助する将来案である。
まだ実装しない。Capability Catalog、Tool schema、Runtime Gateを置き換えず、ActionとSearchを混同しない
評価条件が整ってから検討する。

## 直近の設計・実装で確認すること

* Provider / Builder / Searchの共通契約にTravel固有fieldが入っていないか。
* owner、visibility、purposeを検索前に適用しているか。
* 0件、複数件、stale、削除、権限変更、検索障害を扱えるか。
* Entity Resolution後にRepositoryから正本を再取得しているか。
* Learning Eventが会話全文を無条件保存していないか。
* Enrichment候補にsource、confidence、approval、visibility、失効経路があるか。
* write / ActionがPermission、Confirmation、Auditを通るか。

## 未実装として扱うもの

* 完全なOrchestrator v2 / Capability Catalog
* Activation RAGの永続indexとProvider lifecycle
* Provider横断の完成したEntity Resolution
* Knowledge Enrichment Engine
* Memory / Photo / Calendar Provider
* Capability Usage RAG
* 実ユーザー認証と一般ユーザー向けConfirmation UI

## 優先して読む資料

* `00_project_overview.md`: 全体の現在地
* `01_jarvis_constitution.md`: 判断原則
* `02_jarvis_architecture.md`: 責務境界
* `06_jarvis_chat_next_phase.md`: Chatの完了点と次フェーズ
* `07_activation_rag.md`: Activation RAGの引き継ぎ要点
* `99_handoff_summary.md`: この要約

詳細の正本は `docs/chat_core.md`、`docs/context_assembly.md`、`docs/activation_rag.md`、
`docs/knowledge_enrichment.md` と現行コードで確認する。実装判定は引き継ぎ要約だけに依存せず、README、
通常docs、コードと照合する。

## Jarvis Principle Check

1. Web UIから利用できるか: Chat / Jarvis Shellから利用できる設計である。
2. API / Toolとして利用できるか: Chat API、Runtime API、Core service境界から利用できる。
3. 将来MCP Tool化できるか: Provider中立契約とRuntime境界を保てば可能。
4. Jarvis Coreから呼び出せるか: Activation SearchはCoreのread-only補助として呼び出す。
5. UI依存のロジックになっていないか: 判断・検索・実行はCore / Provider / Runtime / Repositoryに置く。
6. 読み取り系か更新系か: Activation検索はread。索引・Enrichmentは派生データ更新。Domain writeではない。
7. 副作用・権限・プライバシー上の注意: 家族情報、位置、写真、予定を扱うため検索前認可、最小化、
   Forget / visibility連動が必要。Action / Domain writeは確認と監査を必須にする。
