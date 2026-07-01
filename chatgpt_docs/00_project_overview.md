# Jarvis Project Overview

更新日: 2026-06-30

## この資料の用途

`chatgpt_docs/` は、次回のChatGPTへJarvisの現在地、設計思想、次に作るものを引き継ぐための資料である。
単なるREADME / `docs/` の要約ではない。実装済み、現在の制約、将来案を区別し、詳細や最終判断が必要な
場合は通常の `docs/` とコードを確認する。

## 一文での現在地

Basic Chatの復元は完了した。開発の中心はTravel Chat改善から、Jarvis Coreを中心とした
Activation RAG、Entity Resolution、Knowledge Enrichmentへ移った。

## Jarvisとは

Jarvisは、家族の日常、旅行、写真、予定、家、庭、開発作業を自然な対話から扱うPersonal AI Systemを
目指す。Travel、Photo、Calendar、Memory、HomeはJarvisが利用するCapability / Skillであり、Jarvis
そのものではない。

基本思想は **LLM First** である。

* LLMは発話の意味、必要なCapability、Evidenceの十分性、回答を判断する頭脳である。
* PythonはRuntime、Permission、Confirmation、Audit、Validation、Repository、決定的なデータ整形を
  担う実行基盤である。
* Pythonのキーワード分岐を増やして自然言語理解を代替しない。
* Tool実行は必ずRuntime境界を通し、UIやLLMからDB・外部サービスを直接操作しない。

## Chatの現在地

現在の主経路は次の責務分担になっている。

```text
Basic Chat
  -> Router
  -> Runtime（Capability / Toolが必要な場合）
  -> Evidence
  -> Final Answer LLM
```

通常会話はRouterからToolなしのBasic Chatで完結する。Travel等のユーザー固有データが必要な場合だけ
Runtimeへ進み、Repositoryから再取得したEvidenceをFinal Answer LLMへ渡す。Python頭脳は主経路から
大きく除去済みであり、残るSkill固有fallbackは可用性のためのAdapter内fallbackとして扱う。

## Activation RAG

Activation RAGは、**DBを思い出すための索引**である。DB、Repository、Runtime、Evidenceの代替ではない。

* Repositoryが唯一のSource of Truthである。
* RAG Documentと検索indexは破棄・再構築可能な非正本である。
* 検索結果は未検証候補であり、Entity確定、回答根拠、Tool実行許可ではない。
* 候補採用後もRepositoryから正本を再取得し、必要ならRuntimeを通す。
* 検索失敗時はBasic Chatを壊さず、候補なしで続行する。

Travelは「Travel RAG」ではなく、Jarvis Activation RAGの最初のProvider / PoCである。Travel固有の型、
語彙、ranking規則をCoreへ入れない。将来はMemory、Photo、Calendar、Garden等を同じProvider契約へ
載せられる構造にする。

詳細は `07_activation_rag.md`、正本の設計基準は `docs/activation_rag.md` を参照する。

## Knowledge Enrichment

今後は、会話、失敗検索、曖昧検索、ユーザー修正・選択からLearning Eventを作り、検索用の
`alias`、`tag`、`relation`、検索Documentを育てる。

これは本体DBの学習更新ではない。候補は出所、confidence、visibility、承認状態を持つ別の派生Storeで
管理し、承認済み情報だけを検索Documentへ投影する。本体DBの修正が必要な場合は、別の明示的Domain
writeとしてPermission、Confirmation、Auditを通す。

## Capability Usage RAG

将来の検討事項として、Entityの思い出検索だけでなく「Skill / Toolをどう使うか」の承認済み利用例を
RAG候補にできる可能性がある。

* 「テレビつけて」: Home Action
* 「神戸で何した？」: Travel read / memory search
* 「写真ある？」: Photo read

Action ToolとMemory / Domain Searchは別設計である。Capability Usage候補はTool callや実行許可ではなく、
Capability選択を補助するだけにする。これは未実装であり、現フェーズでは実装しない。

## 現在の主要な実装状態

実装済み:

* FastAPI、モバイル向けJarvis Shell、`POST /api/chat`
* Basic Chat RouterとTravel Skillへの分岐
* Runtime、Tool / Skill Registry、Permission、Confirmation、Audit、Validation
* Weather、Travel、PhotoのExecutor / Repository境界
* Evidenceを使うFinal Answer LLM経路
* Activation RAG共通Document、in-memory lexical index、Travel Provider PoC、read-only候補注入
* Travel SQLite、Experience中心モデル、Photo / Immich連携、Travel Web UI

未実装または次フェーズ:

* 完全なJarvis Chat Orchestrator v2とCapability Catalog
* Activation RAGの永続index、Provider lifecycle、他Domain Provider
* Entity ResolutionのProvider横断共通化
* Knowledge Enrichment Engineとreview / approval workflow
* Memory / Photo / Calendar Provider
* Capability Usage RAG
* 一般ユーザー向けConfirmation UIと実ユーザー認証

## 開発ロードマップ

優先順位は次の通り。

1. Activation RAG Core
2. Travel Provider改善
3. Entity Resolution
4. Knowledge Enrichment
5. Memory Provider
6. Photo Provider
7. Calendar Provider
8. Capability Usage RAG検討

Travelの個別Chat機能を増やすことを先行させず、Provider中立なCore契約、正本再取得、認可、評価を先に
固める。

## 引き継ぎ時に優先して読む資料

1. `00_project_overview.md`
2. `01_jarvis_constitution.md`
3. `02_jarvis_architecture.md`
4. `06_jarvis_chat_next_phase.md`
5. `07_activation_rag.md`
6. `99_handoff_summary.md`

Skillの現行詳細が必要な場合は `03_travel_skill_current.md`、`04_photo_skill_current.md`、
`05_developer_workflow.md`、`90_current_status.md` を追加で読む。通常docsでは `docs/chat_core.md`、
`docs/context_assembly.md`、`docs/activation_rag.md`、`docs/knowledge_enrichment.md` を優先する。
