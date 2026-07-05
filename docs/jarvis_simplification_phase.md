# Jarvis Simplification Phase

更新日: 2026-07-05

## 目的

このPhaseでは既存Travel Chatの機能維持より、Pythonから自然言語の意味理解、推論、分類、意図補正、
Entity自動確定を撤去することを優先する。Pythonはschema validation、Runtime、Permission、Confirmation、
Audit、Repository / DB access、決定的なID・型検証、structured result整形、provenance、redactionを担う。

## 2026-07-05に停止したPython頭脳

* `_extract_trip_name`: 発話のsuffixや旅行語を見て旅行名を抽出する処理を削除した。
* `_is_legacy_answer_question`: 「何した」「何食べた」「食事」等からtimeline要否を分類する処理を削除した。
* Planner v1互換補完: `goal`、`answer_mode`、`required_evidence`がないproposalをPythonで
  `clarify / none / []`へ補完する処理を削除した。不完全なproposalは実行しない。
* Travel Entity Resolver: Python lexical searchによる候補rankingと、1候補時の`resolved`自動確定を停止した。
* Plan Executorの自動Tool連鎖: `entity_query`からTripを確定し、`get_trip`または
  `get_trip_timeline`へ進む処理を停止した。
* Composerの意味判断fallback: `answer_mode`から候補理由を`query_too_broad`と判断する処理を削除し、
  既存schemaの構造的状態`missing_context`だけを返す。
* Travel Chat互換経路全体: Router、Travel Planner、Plan Executor、Entity Resolver、Answer Generator、
  Response Composer、legacy Chat Adapterを削除した。
* `/api/chat`からTravel Tool実行を削除した。単一LLM Agent Loopがない間はToolなしBasic Chatだけを返す。

Routerの自然言語分類、PlannerのTool / Operation選択、最終回答は現時点でもLLMが担う。Final Answer
GeneratorはPython固定回答へ戻さず、Runtime由来EvidenceだけをLLMへ渡す。LLM失敗時のPython処理は、
成功を装わず構造的な失敗・確認要求を返すだけに限定する。

## 一時的なダウングレード

名前、地域、memoだけを含む発話からPythonがTrip IDを決めなくなった。LLMが正本IDを持たず
`get_trips + entity_query`を提案した場合、Runtimeで正本一覧を取得するが、Pythonはqueryを解釈せず、
候補を未確定のまま返して停止する。

弱くなった例:

* 「福岡旅行を開いて」: 一覧候補の提示で止まり、自動でTrip画面を開かない。
* 「福岡旅行で何食べた？」: timelineを自動取得せず、Trip選択が必要になる。
* 「神戸旅行で何した？」: title、地域、prefecture、memoのlexical一致で別名Tripを確定しない。
* 「2日目は？」: verifiedな`selected_trip_id`がConversation Stateにある場合だけ既存の
  `get_trip`検証後にtimelineを取得できる。発話だけから日別対象をPythonで推定しない。
* Planner v1形式のproposal: structured planning項目がないためToolを実行しない。

旅行一覧、正本Trip IDを持つ`get_trip`、verified selected Trip IDを使うtimeline read、Runtimeの
Permission / Confirmation / Audit、Repository / DB readは維持する。

2026-07-05の破壊的整理後は、上記Travel read/writeはRuntime API、Travel API、Web Travel画面から利用できるが、
Chatからは利用できない。ChatのTravel route、候補提示、Trip deep link、会話contextによる継続質問、
Travel固有回答生成は停止した。Basic Chat自体は維持する。

## Provider / Operation-first整理

共通`DomainProvider` / `OperationContext`契約を追加し、`TravelProvider`へOperation dispatchとRepository呼び出しを
移した。`TravelExecutor`はRuntime Tool metadataをProvider契約へ変換するadapterだけを担う。Operation catalogの
正本は既存Tool JSONであり、別metadataは追加しない。詳細は[Domain Provider Contract](provider_contract.md)。

## LLM Agent Loopでの復帰条件

Pythonキーワード分岐を戻さず、単一LLM Agent Loopが次を行う。

1. Capability CatalogとTool schemaからTravel Operationを選ぶ。
2. Repository由来候補を未検証候補として観察し、必要ならユーザーへ選択を求める。
3. 選択済みのcanonical `trip_id`を含む次のstructured tool callを生成する。
4. RuntimeがID・schema・Permission・Confirmationを再検証してToolを実行する。
5. Agent Loopがprovenance付きstructured evidenceの十分性を判断し、追加Toolまたは最終回答を選ぶ。

必要なOperation / structured plan項目:

* Operation: `travel.list_trips`, `travel.get_trip`, `travel.get_trip_timeline`
* `tool_id` / operation ID
* schema適合済み`arguments`（確定後はcanonical `trip_id`）
* `required_evidence`（例: `trip`, `timeline`）
* unresolved entity queryと、候補選択が必要であることを表す明示state
* principal / role、confirmation state、step budget
* Tool result provenance、取得元、実行時刻、canonical entity ID

Repository / Runtimeが保持する正本:

* Trip、Experience、timeline、写真linkのcanonical IDと現行record
* visibility / ownership等のaccess control情報
* Tool schema、risk、confirmation、audit要件
* Runtime実行結果とprovenance
* verified selected entity state。検索index、LLM出力、表示labelだけを正本にしない。

## 残る移行対象

* `TravelSearchIndex`とActivation RAG lexical indexは候補想起用として残る。候補をEvidence、Entity確定、
  権限、Tool実行許可へ昇格させてはならない。
* 単一LLM Agent Loop、Agent用Operation catalog view、server-owned session / confirmation stateは未実装。
