# Jarvis Chat: Current State and Next Phase

更新日: 2026-06-30

## 結論

旧資料が前提としていた「Jarvis Chat v0.1開始前」の段階は終了した。Basic Chatの復元、Routerによる
通常会話とTravelの分離、Runtime経由のTravel read、Evidenceを使うFinal Answer LLMは実装済みである。

次フェーズの中心はTravel Chatのユースケース追加ではない。Jarvis CoreのActivation RAG、Entity
Resolution、Knowledge EnrichmentをProvider中立に育てることである。

## 現在の会話経路

```text
User Message
  -> Basic Chat / Context
  -> Router（LLM判断、server-side validation）
       -> direct answer: ToolなしでBasic Chat回答
       -> capability required: Skill Adapterへ
  -> Runtime Gate
       Validation / Permission / Confirmation / Audit / Execution
  -> Repository canonical read
  -> Evidence Assembly
  -> Final Answer LLM
```

短く表すと次の構成である。

```text
Basic Chat -> Router -> Runtime -> Evidence -> Final Answer LLM
```

ただしRuntimeは全Turnへ強制しない。通常会話はToolなしで完結し、ユーザー固有データやActionが必要な
場合だけRuntimeへ進む。Routerが失敗・不正出力になった場合も、Travel Toolを推測実行せずBasic Chatへ
安全にfallbackする。

## LLM Firstの現状

LLMが次を判断する。

* 通常知識だけで答えられるか
* ユーザー固有データが必要か
* どのCapabilityを使うか
* Evidenceが質問に十分か
* どう答えるか、または何を聞き返すか

Pythonは次を担う。

* Context Assemblyと構造化出力の検証
* Runtime、Permission、Confirmation、Audit、Validation
* Tool実行とRepository境界
* 候補数、schema、上限、Evidenceの決定的な整形
* timeout、fallback、ログ、再現可能な安全Policy

Pythonによる自然言語キーワード分類や固定語彙回答は主経路の頭脳にしない。既存のTravel固有Plannerや
deterministic fallbackはTravel Adapter内に閉じ、Final Answer LLM失敗時など限定条件でのみ使う。

## Activation RAGをChatへどう置くか

Activation RAGはRouter / Entity Resolution前後の軽量な候補想起であり、正本やEvidenceではない。

```text
User Message + authorized scope
  -> Activation RAG
  -> unverified candidates
  -> Router / Entity Resolution
  -> Runtime（必要な場合）
  -> Repository canonical read
  -> Evidence
  -> Final Answer LLM
```

候補のscore 1位を自動確定しない。`entity_id`をRepositoryで再検証し、0件・複数件・stale・権限不一致を
扱う。検索障害はChat応答の失敗条件にしない。

Travelは最初のProvider / PoCである。Chat CoreがTravelの`trip_id`、地名辞書、日程規則を理解する設計に
しない。Memory、Photo、Calendar、Gardenも同じ共通envelopeへ接続できるようにする。

## 次に作るもの

1. **Activation RAG Core**: Provider / Builder / Search契約、認証主体・visibility・purpose、再構築と
   失効、検索障害分離を固める。
2. **Travel Provider改善**: zero-result、曖昧性、stale Document、削除、visibility変更を評価し、
   Travel固有処理をProvider内へ保つ。
3. **Entity Resolution**: RAG候補を正本Entityへ安全に解決する。候補提示、確定、再取得を分ける。
4. **Knowledge Enrichment**: 会話、失敗検索、ユーザー修正からalias / tag / relation / 検索Document候補を
   作り、承認後だけ索引へ反映する。
5. **Memory Provider**
6. **Photo Provider**
7. **Calendar Provider**
8. **Capability Usage RAG検討**

## 現フェーズで実装しないもの

* Capability Usage RAG
* RAG検索結果からのAction自動実行
* EnrichmentからTravel等の本体DBへの自動書き戻し
* Travel固有schemaのJarvis Coreへの追加
* score 1位や単一候補を根拠にした権限・確認・正本再取得の省略

## Capability Usage RAGの検討境界

将来、Capability Catalogが大きくなった場合、承認済みの利用例を別corpusで検索する可能性がある。

| 発話 | 候補 | 次の境界 |
| --- | --- | --- |
| 「テレビつけて」 | Home Action | Home Tool schemaとRuntime Gate |
| 「神戸で何した？」 | Travel read | Entity ResolutionとRepository read |
| 「写真ある？」 | Photo read | Photo Provider / Photo Tool |

Action ToolとMemory / Domain Searchは別設計である。usage候補はCapability選択のhintに留め、Tool call、
引数、実行許可を生成しない。導入判断にはCatalog fallback、version失効、承認workflow、Action / Search
誤分類の評価が必要である。

## 安全とプライバシー

* OpenAI API Keyと認証情報はserver-sideに置く。
* RuntimeをTool実行の唯一の経路にする。
* RAG検索前に認可・visibility・purposeを適用する。
* LLM、debug、Auditへ送る候補本文と家族情報を最小化する。
* write / Actionは明示対象、差分、権限、確認、監査を要求する。
* Learning Eventへ会話全文を無条件保存しない。
* source削除、Forget、権限変更に索引とEnrichmentを連動させる。
