# Jarvis Chat Core / Orchestrator v2

## Status and priority

本書は、既存のChat Core v0.3 Foundation / Travel Planner v2を残しながら、Jarvis全体の
会話入口を立て直すための上位方針を定める。Basic Chat Router v0.1では、LLMの検証済み判定により
通常会話をToolなしで回答し、Travel固有の発話だけ既存Travel Chatへ委譲する入口を実装した。
完全なOrchestrator v2、Memory RAG、Capability Catalog、Knowledge Enrichmentは未実装である。

最優先はBasic Chatの復元である。成長順は次を守る。

1. 普通の会話が成立する
2. Working ContextとMemoryを踏まえた会話ができる
3. 単一Capabilityを使った会話ができる
4. 複数Capabilityを連携した会話ができる

Jarvisは旅行アプリのチャット機能ではない。Jarvisは通常の挨拶、時刻、自己説明、一般的な
質問へ自然に答えられるAIであり、Skillは会話を助ける部品である。Travelの精度向上がBasic
Chatを退化させる構成は採用しない。

## Core principles

### LLM is the brain; Python is the execution substrate

LLMは、通常知識だけで答えるか、ユーザー固有データが必要か、どのCapabilityを使うか、
Evidenceが十分かを判断する。PythonはPrompt / Context Assembly、Catalog生成、出力検証、
Runtime Gate、Permission、Confirmation、Audit、Tool実行、Evidence整形、会話ログと学習イベントの
記録を担当する。

Pythonに「ご飯」「写真」「何した」のような自然言語キーワード分岐を足して知能を作らない。
決定的なschema検証、安全Policy、日付計算、正規化はPythonの責務だが、発話の意味判断はLLMの
責務とする。Skill固有の決定的fallbackが必要な場合もCoreではなくAdapter内に閉じ、評価ケースと
廃止条件を持たせる。

### Expose capabilities, not implementation units

内部のSkill、Tool、ExecutorをそのままLLMの世界モデルにしない。LLMへは「家族の旅行記録を
扱える」「写真を検索できる」「過去の思い出を参照できる」のようなCapability Catalogを渡す。
当面は全Capabilityの概要を毎Turn提示し、Pythonが発話から候補Skillを先に絞らない。

Capabilityが増えたら、第一段階で全Capabilityの存在と選択条件を提示し、LLMが選んだCapabilityだけ
第二段階でTool schemaと制約を追加する。選択後のTool実行は必ずRuntime Gateを通す。詳細は
[Context Assembly](context_assembly.md)を参照する。

## Orchestrator v2 target flow

```text
Receive User Message
  -> Context Assembly
       System / Personality / User Profile / Working Context
       Memory RAG / Capability Catalog / Current World / User Message
  -> LLM Turn
       direct_answer | need_capability_detail | tool_call | clarification
  -> Capability Detail on Demand
  -> Runtime Gate
       validation | permission | confirmation | audit | execution
  -> Evidence Assembly
  -> Final LLM Answer
  -> Learning Event
       conversation | failure | correction | ambiguity | enrichment candidate
```

通常会話は`direct_answer`としてToolなしで完結できる。時刻などCurrent Worldで回答できる質問も、
Travel Plannerへ入れない。Capability詳細の要求とTool callは別段階とし、LLMがCapabilityを選んでも
Pythonがそのまま実行を許可するわけではない。Evidence取得後の最終回答はEvidenceに基づき、
不足時は推測せず質問する。

中心部品はPlannerではなくContext Assemblyである。Planner / Goal-aware Planningは、複数stepや
Skill固有の探索が必要なTurnで使う任意部品へ下げる。全TurnへPlan作成を強制しない。

## Core and adapter boundary

Chat Coreが所有するもの:

* Context Assemblyと入力予算
* LLM Turnの共通出力契約
* Capability Catalogと詳細取得の調停
* Runtime Gateへの唯一の実行経路
* Skill非依存のEvidence Assembly
* Final AnswerとLearning Eventのライフサイクル

Travel Skill Adapterへ置くもの:

* Travel Capabilityの説明と詳細Tool定義
* Travel Entity Resolution、Search / Enrichment接続
* Travel固有のEvidence変換
* 必要な場合だけ使うTravel Planner / Goal契約 / Plan Executor
* Travel Answer Generatorの決定的fallbackとTravel固有表示支援

既存のTravel Planner、Goal-aware Planning、Travel Answer Generator、Travel Plan Executor、Travel
Search Index、Entity Resolverは無駄ではない。ただしChat入口の主役ではなく、Travel Capabilityを
選択した後に呼ばれるAdapter実装へ位置づけ直す。

## Current code risk review (2026-06-29)

* **TravelのChat Core占有: v0.1で入口を分離済み。** `POST /api/chat`は`handle_chat()`を呼び、
  LLMがTravel Skillを選んだ場合だけ`handle_travel_chat()`へ委譲する。Travel内部のPlanner、Resolver、
  Executor、Answer Generator、Composerは既存Adapterとして維持している。
* **通常会話のTravel Planner流入: v0.1で解消。** Basic Chatは`direct_answer`としてToolなしで回答する。
  Router出力が不正またはLLM呼び出しが失敗した場合も、Travel Runtimeを起動しないBasic側へfallbackする。
* **Pythonが自然言語理解を持ちすぎている: confirmed / medium.** Planner本体は意味判断をLLMへ
  寄せている一方、`travel_plan_executor.py`と`travel_answer_generator.py`には「何した」
  「何食べた」「食事は」、日数、食事語彙による再分類・抽出が残る。これはTravel Adapterの
  bounded fallbackとしては利用可能だが、Core判断へ昇格させない。
* **Capability Catalogが未整備: confirmed / high.** `skills/*/skill.json`と`tools/*/*.json`は
  Registry / Runtime用の実装メタデータであり、LLM向けCapabilityの要約、利用条件、Evidence種別、
  privacy分類、詳細取得IDという契約がない。Travel PlannerにはTravel Tool allowlistだけが渡る。
* **Memory RAGがない: confirmed / high.** Working Contextは最大5件のclient-provided履歴だけで、
  Memory検索、ranking、ownership / visibility filter、候補注記がない。過去の訂正、好み、思い出を
  通常Turnで想起できない。
* **Knowledge Enrichmentがない: confirmed / high.** Search Expansionは固定辞書、Search Indexは
  現在データからのrule-based索引である。Trip、Experience、Location、Photo、会話訂正を横断した
  意味リンクや、出所・confidence付き派生情報を蓄積できない。
* **Goal-aware PlanningはAdapterへ移せる: feasible with boundary work.** `Plan`型自体はSkill-neutral
  だが、公開Orchestratorの配線、Planner prompt、Tool policy、Executor、Answer modeはTravel固有で
  ある。Travel Capability選択後のAdapterへFacadeごと移し、Coreは共通Turn契約だけを扱える。
* **Registryは実行と表示には使えるが選択モデルではない: confirmed / medium.** Skill JSON、Tool
  JSON、ExecutorRegistry、RuntimeServiceは存在し、安全な実行基盤になる。一方、Catalog生成、
  Adapter登録、CapabilityからTool詳細への解決は未実装である。

## Phased implementation plan

1. Basic Chat regression casesを先に固定する。「おはよう」「今何時？」「あなたのバージョンは？」と
   Travel代表ケースを、live APIに依存しないcontract test / evalへ追加する。
2. Context Assemblyと共通LLM Turn schemaを最小実装し、`direct_answer`と`clarification`をToolなしで
   返せる入口を作る。Current Worldにはserver-side現在日時とtimezoneを含める。
3. 既存Skill metadataから手書きの小さなCapability Catalogを分離し、全概要提示から始める。
4. Travel配線をTravel Skill Adapterへ包み、選択後だけ既存Planner / Executorを呼ぶ。既存API互換は
   Facadeで維持する。
5. 権限filter済みMemory RAGをread-onlyで追加し、毎Turn上位3〜5件を参考候補として渡す。
6. Capability detail on demandと複数Capability Evidence Assemblyを追加する。実行はRuntime以外を
   通さない。
7. Learning Eventを記録し、その後にKnowledge Enrichment候補生成を別worker / 境界で追加する。
   DB schema、自動適用、Memory化はそれぞれ別設計・別変更とする。

## Non-goals for this review

Orchestrator v2実装、DB / Memory / Enrichment実装、OpenAI live eval、既存コード削除、大規模
リファクタ、service restartは今回行わない。

> 次フェーズのChat Core v0.3 Response IntelligenceとTravel Answer Generator v0.1の
> 設計・Effort Policy・実装準備は
> [Chat Core v0.3: Response Intelligence](chat_response_intelligence.md)を参照する。
> Planner v2とTravel Answer Generatorは実装済みである。Photo連携、Memory、Replannerは
> 引き続き将来範囲とする。

Chat Core v0.2 Foundationは、Chatの賢さや対応Toolを増やす変更ではない。
Entity Resolution、Response Composer、Photo連携、Pending Actionを追加する前に、
`chat_orchestrator.py`へ集まり始めた責務を分離するための内部契約を定義する。

設計判断の詳細は
[Chat Core Skill Adapter Architecture](decisions/2026-06-chat-core-skill-adapter-architecture.md)を参照する。

## 目標: Skill接続ではなくSkill連携

Jarvisの目標は、ユーザーの発話を単一のSkillやToolへ中継することではない。
意図を補完し、会話の作業状態を保ち、必要なSkillから候補を探し、結果を人間向けの
応答へまとめることで、複数の能力を一つの会話として連携させる。

ユーザーにTool名、Skill境界、Tool結果のJSONを意識させない。Jarvis Coreは共通の
会話プロトコルとオーケストレーションを担当し、Skill固有の解釈と変換はChat Skill
Adapterへ委譲する。

```text
自然なユーザー発話
        ↓
Chat Core（文脈、計画、共通プロトコル）
        ↓
Chat Skill Adapter（Skill固有の候補解決、入出力変換）
        ↓
Plan Executor（bounded step、Tool policy、Runtime実行制御）
        ↓
Runtime（Permission / Confirmation / Audit）
        ↓
Skill
        ↓
Response Composer（人間向け応答）
```

ここでいうChat Skill Adapterは、Chat CoreとSkillの会話上の境界である。
外部APIの詳細を隠すExternal Adapterや、Runtimeから呼ばれるSkillExecutorとは別の責務を持つ。

## Coreを太らせない

Skillが増えるたびにChat CoreへSkill名やTool IDによる`if`分岐を足し続けない。
Coreが持つのは、Conversation State、Entity Resolution、Plan / Execute、Response Composerの
共通プロトコルとライフサイクルである。

Skill固有の責務はChat Skill Adapterへ置く。

* Skill固有Entityの候補検索と正規化
* Entity候補の表示名や曖昧性の表現
* Skill固有slotと`EntityRef`の相互変換
* Runtime / Tool結果からSkill固有`content_blocks`への変換
* Skillに適した`SuggestedAction`候補の組み立て

CoreにSkill固有分岐が増え始めた場合は、機能追加を続ける前に共通プロトコルかAdapter境界を
見直す。

## 4層の責務

1. Conversation State
   - `ConversationState`が現在のSkill、選択Entity、Skill固有slotを保持する。
   - Entityは`EntityRef`で表し、出所と検証時刻を区別する。
2. Entity Resolution
   - `EntityResolutionRequest`、`EntityResolutionResult`、`EntityResolver` Protocolを共通入口にする。
   - Entity ResolutionはSkill横断の共通概念だが、候補の探し方、正規化、順位付けなどの詳細は各Chat Skill Adapterが担当する。
   - Resolverは検索候補を`resolved`、`ambiguous`、`not_found`、`needs_context`の解決状態へ変換する。
3. Plan / Execute
   - `Plan`と`Planner.create_plan()`を、LLM提案から実行判断を分離する共通契約とする。
   - `TravelPlanner`はLLM提案を検証済み`Plan`へ変換するだけで、Resolver、Runtime、検索、score判定、Tool実行、Response生成、Conversation State更新を行わない。
   - Planはintentに加えて、最終目的`goal`、回答形式`answer_mode`、必要な根拠`required_evidence`を保持する。Tool候補、対象Skill／Entity type、context／resolution／confirmation要否、理由、confidenceも従来どおり保持する。
   - `PlanExecutor.execute(ExecutionRequest)`がPlanを受け取り、bounded loop、Chat Tool Policy、Entity Resolver、Runtime実行を調整する。
   - `ExecutionResult`は実行状態、Runtime／Resolution結果、最終Tool ID／arguments、step、更新後Conversation State、diagnosticsをComposerへ渡す。
   - Chat / LLMはExecutorやRepositoryへ直接到達せず、Runtimeを迂回しない。
4. Clarification / Response Composer
   - `ClarificationPolicy`が実行後の`query_too_broad`、複数候補、low confidence、文脈不足を`ClarificationResult`へ変換する。
   - 候補はRuntime結果またはResolverの既存候補だけを使い、検索、解決、Tool実行を行わない。
   - `ResponseComposer.compose(ComposeRequest)`を共通入口とし、`ComposeResult`でlegacy互換responseと内部`ChatResponseV1`を返す。
   - `ChatResponseV1`、`ContentBlock`、`SuggestedAction`を内部応答契約とする。
   - Tool結果をそのままUIへ渡さず、会話文、表示可能なcontent block、次の選択肢へ変換する。
   - `TravelResponseComposer`がTravel固有の文言、候補、navigation、Runtime TripからのConversation State更新を担当する。
   - `legacy_chat_response_to_v1()`とSkill別Composerで公開APIを変えずに段階移行できる。

## Response Composer Protocol v0.1

`ComposeRequest`はOrchestratorが確定した事実だけをComposerへ渡す。現在はoutcome、ユーザー発話、Plan、
Entity Resolution結果、Runtime結果、Conversation State、Tool ID／arguments、候補、許可済みの
navigation hint、diagnosticsを保持できる。Composerはこの入力を表示用responseへ変換するだけで、
Planner、Entity Resolver、Runtime、OpenAIを呼ばない。Permission／Confirmation判断、bounded step、
debug timing、公開直前のsecret redactionもOrchestratorに残す。

`ComposeResult`は次の2形式と更新後Conversation Stateをまとめて返す。

* `response`: 現行`POST /api/chat`用のlegacy互換dict
* `response_v1`: 将来のSkill横断API向け`ChatResponseV1`
* `conversation_state`: Runtimeで確認できたEntityを反映した更新後state

`ClarificationResult`は`status`、人向けの`clarification`、`candidate_list`、`reason`、
`recommended_action`を持つ。Travelでは広すぎる質問には全候補、`どれか`／`最近`には
旅行日が新しい3件、複数候補には選択要求を返す。これは候補表示の対話制御であり、
SearchDocument、SearchEngine、Planner、Resolverの精度や判定を変更しない。

`TravelResponseComposer` v0.1は`get_trips`の一覧、`get_trip`の詳細と安全なTravel navigation、
複数Trip候補、未検出、pending write、および既存のTravel read Tool成功文言を担当する。
Trip詳細のRuntime結果から検証済みConversation Stateも生成する。候補検索やTrip実在確認はせず、
それらは従来通りOrchestratorからResolver／Runtime境界を通す。

公開レスポンスは従来の`action`と`candidates`を維持し、clarification時に`clarification`を追加する。
`clarification`は`ClarificationResult`のJSON表現である。既存の`tool_id`、`arguments`、`result`、
`navigation`、`updated_context`、`debug`は変更しない。`response_v1`は内部結果であり、今回の
公開APIには追加しない。将来Travel以外を追加するときは同じProtocolを実装する
`PhotoResponseComposer`、`CalendarResponseComposer`、`GardenResponseComposer`を追加し、Coreに
Skill固有の表示分岐を持ち込まない。

## Plan Executor Protocol v0.1

### Planner v2: Goal-aware Planning

Planner v2は新しいPlanner部品を増やさず、既存`Plan`を次の3フィールドで拡張する。

| field | 役割 | Travelでの値 |
| --- | --- | --- |
| `goal` | ユーザーが最終的に達成したいこと | Travelでは`open_trip`、`summarize_trip`、`summarize_day`、`summarize_meals`、`show_photos`、`clarify` |
| `answer_mode` | Answer Generatorの回答形式 | Travelでは`none`、`summary`、`day_summary`、`meals`、`photos`、`clarification` |
| `required_evidence` | 回答前にRuntime経由で必要な根拠 | Travelでは`trip`、`timeline`、`experience`、`photo` |

Coreは3フィールドをSkill非依存の文字列契約として運搬し、許可値と組合せは各Skill Plannerが
検証する。Travel語彙をCoreの型へ固定しないため、Photo / Calendar / Gardenは独自のGoal契約を
追加できる。既存呼び出しとの互換性のためdefaultを持つ。Plannerは現在発話を主入力としてGoalを判定し、
Conversation Working ContextとConversation Stateは省略を補うヒントに限る。現在発話に旅行名が
明示されている場合、選択中旅行で上書きしない。

名前付き対象はLLM提案の`entity_query`を検証後に汎用`Plan.resolution_query`として保持する。
Executorは発話を再解釈してToolを増やすのではなく、`required_evidence`を満たすよう既存Toolを
並べる。要約系は名前付き旅行なら`get_trips → get_trip_timeline`、選択中旅行なら実在確認を含む
`get_trip → get_trip_timeline`をRuntime境界内で実行する。`open_trip`は従来の
`get_trips → get_trip`を維持する。

`show_photos`は`trip / experience / photo`が必要だとPlanへ表現するが、Planner v2ではPhoto Skillを
追加しない。体験IDと既存写真Toolが利用可能な経路は維持し、対象体験の写真連携がない場合は
未対応という一般論ではなく、不足Evidenceを説明する。

`ExecutionRequest`は、検証済みPlan、ユーザー発話、Conversation State、server-owned role、
debug flag、Runtime Service、任意のResolver、最大step数を保持する。RuntimeとResolverは
Executorの依存境界として渡し、PlanやLLM出力から選ばせない。

`ExecutionResult`はユーザー向けresponseではなく、Composerへ渡す実行上の事実だけを保持する。

* `execution_status`: success、needs_context、pending_write、candidates、not_found、
  runtime_error、permission_denied、max_steps
* `runtime_result` / `resolution_result`
* 最終`tool_id` / `arguments`と実行済み`steps`
* 更新後`conversation_state`、候補、context clear指示、diagnostics

`TravelPlanExecutor` v0.1は既存Travelフローだけを担当する。選択中Trip参照のserver-side補正、
名前付きTripに対する`get_trips`後の`TravelEntityResolver`呼び出し、解決済みTripの
`get_trip`実行、timeline前のTrip実在確認、最大step制御を行う。すべてのread実行は直前に
Chat Tool Policyで再検証し、必ずRuntimeへ`confirmed=False`とserver-owned roleを渡す。
write ToolはRuntimeへ渡さず、既存のpending状態を返す。

ExecutorはLLM／OpenAI呼び出し、応答文言、content block、navigation、公開response、最終secret
redactionを担当しない。Permission／Confirmationを上書きせず、RepositoryやDBを直接呼ばない。
OrchestratorにはPlanner、Executor、Composerの呼び出し順、debug timing統合、legacy context変換、
公開直前のsecret redaction、API互換responseの返却を残す。

## 入力設計

ユーザー発話は、Tool入力のように完全ではないことを前提にする。省略、言い換え、曖昧な
固有名詞を、直ちにエラーとして扱わない。

たとえば「神戸旅行」に対する「須磨シーワールド」のように、人間なら旅行の文脈から探す
候補をJarvisも探索できる設計にする。ただし、Chat CoreがTravelの検索規則やPlace APIを
直接知るのではない。Coreは解決要求と候補の共通形式を扱い、Travel Chat AdapterがTravelや
必要な関連Skillの境界を使って候補を返す。複数候補が残る場合は根拠なく自動選択せず、
会話で絞り込む。

Entity候補と権限確認済みEntityは区別する。候補解決はアクセス権の証明ではなく、実行前の
検証と認可はRuntimeを含むserver-side境界で行う。

## 出力設計

Tool結果は機械向けの実行結果であり、そのまま会話UIの応答ではない。Response Composerは
結果とConversation Stateを使い、少なくとも次の内部契約へ変換する。

* `message`: 質問へ直接答える人間向けの会話文
* `content_blocks`: Trip、Timeline、PhotoなどをUI非依存の構造で表した補助内容
* `suggested_actions`: 続けて選べる安全な操作候補

「2日目は？」にはtimeline JSONを露出するのではなく、現在のTripと日付を解決したうえで
会話として答え、必要なら予定のblockと次の候補を添える。Composerは表示用DOMを組み立てない。
現行互換の許可済みnavigationはlegacy responseとV1のsuggested actionへ変換し、任意URLや
クライアント実装を受け入れない。これによりWeb UI、API、将来のMCPや音声入口で共通の応答契約を
再利用できる。

## Conversation Stateと信頼境界

Conversation Stateは長期記憶ではなく、会話中の作業状態である。現在見ているTrip、写真、予定、
選択候補などを`EntityRef`として保持する。恒久的なPreferenceや思い出を扱うMemory、Tripや
Photo Assetを所有するSkill DBとは分離する。

### Conversation Working Context v0.1

`ConversationWorkingContext`はPlannerが現在の質問を解釈するための一時的な補助入力であり、
`ConversationTurn(role, content)`を古い順に最大5件保持する。Planner入力は、現在の質問、
Conversation Working Context、Conversation Stateを別々のセクションとして受け取る。現在の質問を
主入力とし、履歴は省略や対象変更の理解を助け、Conversation Stateは選択済みEntityなどの状態ヒントを
与える。対象を決めるrule-based分岐は追加しない。

`POST /api/chat`は任意の`conversation_history`を受け取る。Web UIは成功したuser／assistant発話を
メモリ上で最大5件だけ保持し、次のリクエストへ渡す。サーバーは履歴をDB、Conversation State、
監査ログへ保存しないため、ページ再読み込みで破棄される。API利用者も履歴なしで従来どおり呼び出せる。

Working ContextはMemoryではない。将来、重要な会話をMemory候補へ昇格する場合も、Coreが明示的に
候補化し、Memory Skillの権限・確認・保存境界へ渡す。今回の型はその入力元として再利用できるが、
重要度判定、Memory Candidate型、Memory Skill、保存・検索は実装しない。

Conversation Stateから長期保存する内容は自動昇格させず、Jarvis CoreがMemory候補として判断し、
Memory Skillへ委譲する。Core / Memory Skill / Evidence Skillの境界は
[Jarvis Memory Architecture](memory_architecture.md)を参照する。

`travel_chat_adapter.py`は、legacy contextとConversation Stateの相互変換、Trip
`EntityRef`生成、Travel content block生成を担当する。

Browserから受け取る`selected_trip_id` / `selected_trip_title`は互換維持のため残すが、
信頼済み状態ではなく`source=client_context_hint`、`verified_at=None`の未信頼ヒントへ
変換する。これらはEntityの実在やアクセス権を証明しない。特に選択旅行の日程取得では、
従来通りRuntimeの`get_trip`を先に実行して実在確認する。Runtime結果から作るEntityだけが
`source=travel_runtime`と`verified_at`を持つ。

現在のcontext受け渡しはAPI互換のための暫定方式である。将来はserver-ownedの
`conversation_id`を導入し、認証済み主体に紐づくConversation Stateをserver側で管理する。
クライアントから渡されたcontextは、その後も状態更新の根拠ではなくヒントとして扱う。

## Search Engine v0.2

`backend/search_engine.py`はSkill共通の`SearchDocument`と`SearchEngine`を提供する。
`SearchDocument`は`id`、`label`、検索対象の`document`、Skill固有情報を保持できる
`metadata`、重みと一致理由を持つ`keywords`からなる。Search EngineはTripやTravel語彙を
知らず、この共通documentだけを`EntityCandidate`へ変換する。

Travel側の構成は次の通りである。

```text
Trip[]
  -> TravelDocumentBuilder          # Trip -> SearchDocument
  -> TravelSearchExpansionProvider  # Travel語彙 -> SearchTerm
  -> SearchEngine.search()          # SearchDocument[] -> EntityCandidate[]
```

`TravelDocumentBuilder`だけが`title`、`prefectures`、`memo`、日付、`outing_type`を知り、
各フィールドの検索重みを共通keywordへ変換する。`TravelSearchExpansionProvider`だけが
依頼表現と`神戸 -> 兵庫, 須磨`などのTravel語彙を知る。`TravelSearchIndex`はこの3要素を
組み立てる互換Facadeであり、公開済みの`search(query, trips)`を維持する。

現在のrule-based Engineはscoreを`0.0`から`1.0`に制限し、同点時は正規化labelとentity IDで
安定順序にする。将来FTS、BM25、Embedding、Hybrid Searchへ移行するときは、
`SearchDocument[] -> EntityCandidate[]`契約を保った新Engineへ差し替えればよく、各Skillの
Builder、語彙Provider、Chat Core、Travel Adapter公開APIを変更する必要がない。

名前付きTrip要求では、Chatはまず従来通りRuntimeで`get_trips`を取得し、その結果だけをIndexへ
渡す。`TravelEntityResolver`は`TravelSearchIndex`の候補を共通の`EntityResolutionResult`へ
変換する。候補が1件なら候補の実在するTrip IDでRuntimeの`get_trip`へ進み、複数件なら既存の
候補カード用`candidates`を返して自動選択しない。0件なら安全な未検出応答にする。検索候補は
認可証明ではなく、Runtime、Permission、Confirmation、Auditの境界は変更しない。

## Entity Resolver Protocol v0.1

Entity Resolverは、検索品質や検索方式を定義する層ではない。`SearchDocument`がSkill固有データを
検索可能な共通形式へ変換し、`SearchEngine`が順位付き`EntityCandidate`を返し、Resolverが候補数
など既存ポリシーに基づいて解決状態へ変換する。Chat Coreは個別Skillの語彙や検索規則ではなく、
次の共通契約だけを見る。

* `EntityResolutionRequest`: query、任意のskill ID／entity type／context、候補上限
* `EntityResolutionResult`: 解決状態、候補、任意の解決済みEntity、理由、診断情報
* `EntityResolver.resolve(request)`: Skill固有Resolverが実装する共通境界

Travel実装はRuntimeを直接呼ばない。Orchestratorが従来どおりRuntimeの`get_trips`を実行し、
取得できたTripだけを`TravelEntityResolver`へ渡す。Resolverは`TravelSearchIndex`で候補を検索し、
0件を`not_found`、1件を`resolved`、複数件を`ambiguous`へ変換する。score差による新しい自動選択は
行わない。これによりTravelの公開応答とRuntime境界を維持したまま、将来は同じ契約で
`PhotoResolver`、`CalendarResolver`、`GardenResolver`、`MemoryResolver`を追加できる。

追加するSkillでは、Skill固有データを`SearchDocument`へ変換するBuilderと必要な検索語彙Providerを
用意し、共通`SearchEngine`またはSkill固有検索Facadeから得た候補をResolverで解決状態へ変換する。
Chat Core側はResolver登録と共通結果の処理だけを追加し、Skill固有語彙やデータ形式を持たない。

## 安全境界

* BrowserはOpenAI APIを直接呼ばず、server-side Chat APIを使う。
* LLMはRuntime、Executor、Repositoryを直接呼ばず、検証可能な提案だけを返す。
* LLM出力を`role`、`confirmed`、Permission判定、navigation URLの正として採用しない。
* RuntimeがPermission、Confirmation、Auditと安全な実行委譲を担当する。
* CoreはLLMの提案を検証し、Tool実行ではRuntimeを必ず経由する。
* navigationはserver側で許可された識別子やrouteから構築し、LLM生成URLを直接開かない。

ChatのroleはBrowserやLLMが所有しない。互換性のためrequestの`role`フィールドは受理するが
無視し、認証実装まで`/api/chat`はserver側の暫定`admin`をRuntimeへ渡す。
認証導入時は、固定値を認証済みsession/principalから導出する値へ置き換える。

## API互換

`POST /api/chat`は当面、既存の`action`、`tool_id`、`arguments`、`result`、
`navigation`、`updated_context`、`debug`を返す。UIの変更は不要で、内部契約への変換は
追加したComposerで行える。`ChatResponseV1`を公開APIへ切り替えるのは別フェーズとする。

## 今後の設計原則

* まず一つの会話ユースケースを縦に薄く通し、境界が機能することを確認する。
* 実際に動かして見えた責務の歪みをdocsと共通契約へ戻す。
* 増改築している感覚やCoreのSkill固有分岐が増えたら、Core責務を先に見直す。
* 「今作れるか」ではなく「Skillが増えても同じ境界で育つか」で採否を判断する。
* v0.2で未実装の能力を実装済みとして扱わず、Foundationと次フェーズを明記する。

## Legacy foundation extraction candidates

以下は既存Foundationの候補であり、Orchestrator v2のBasic Chat復元より優先しない。
実施順は上記のPhased implementation planに従う。

1. Travel Search Indexのranking実装を、評価データを用意したうえでBM25 / FTS / Embeddingへ差し替え可能にする。
2. `response_v1`のcontent block／suggested actionを利用する内部consumerを追加し、legacy公開形式からの段階移行を検証する。
3. Photo連携と`PhotoResponseComposer`をTravel / Photo双方のAdapter境界を通して追加する。
4. 更新ToolをRuntime確認付きPending Actionへ接続し、Composerのpending responseを実際の確認導線へ拡張する。
5. Skill追加時にResolver／Executor／Composer registryを導入し、CoreのSkill固有配線を増やさない。
