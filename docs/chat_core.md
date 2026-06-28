# Chat Core v0.2 Foundation

> 次フェーズのChat Core v0.3 Response IntelligenceとTravel Answer Generator v0.1の
> 設計・Effort Policy・実装準備は
> [Chat Core v0.3: Response Intelligence](chat_response_intelligence.md)を参照する。
> 現時点では設計のみで、既存挙動はv0.2 Foundationのままである。

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
   - Planはintent、対象Skill／Entity type、Tool候補、context／resolution／confirmation要否、理由、confidenceを保持し、将来のPlanner実装を差し替え可能にする。
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

## 次の抽出候補

優先順は次のとおりとする。

1. Travel Search Indexのranking実装を、評価データを用意したうえでBM25 / FTS / Embeddingへ差し替え可能にする。
2. `response_v1`のcontent block／suggested actionを利用する内部consumerを追加し、legacy公開形式からの段階移行を検証する。
3. Photo連携と`PhotoResponseComposer`をTravel / Photo双方のAdapter境界を通して追加する。
4. 更新ToolをRuntime確認付きPending Actionへ接続し、Composerのpending responseを実際の確認導線へ拡張する。
5. Skill追加時にResolver／Executor／Composer registryを導入し、CoreのSkill固有配線を増やさない。
