# Chat Core v0.2 Foundation

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
   - `EntityResolver` Protocolと`EntityCandidate`を共通入口にする。
   - Entity ResolutionはSkill横断の共通概念だが、候補の探し方、正規化、順位付けなどの詳細は各Chat Skill Adapterが担当する。
   - v0.2では候補型と境界だけを定義し、曖昧検索や自動選択は追加していない。
3. Plan / Execute
   - 現在のproposal検証、bounded loop、Chat Tool Policy、Runtime実行を維持する。
   - Chat / LLMはExecutorやRepositoryへ直接到達せず、Runtimeを迂回しない。
4. Response Composer
   - `ChatResponseV1`、`ContentBlock`、`SuggestedAction`を内部応答契約とする。
   - Tool結果をそのままUIへ渡さず、会話文、表示可能なcontent block、次の選択肢へ変換する。
   - `legacy_chat_response_to_v1()`とTravel用Composerで段階移行できる。

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
会話として答え、必要なら予定のblockと次の候補を添える。Composerは表示用DOMや画面遷移を
組み立てず、Web UI、API、将来のMCPや音声入口で再利用できる応答を作る。

## Conversation Stateと信頼境界

Conversation Stateは長期記憶ではなく、会話中の作業状態である。現在見ているTrip、写真、予定、
選択候補などを`EntityRef`として保持する。恒久的なPreferenceや思い出を扱うMemory、Tripや
Photo Assetを所有するSkill DBとは分離する。

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

1. Travel Entity Resolverを最小の縦切りとして実装し、候補選択policyを確立する。
2. legacy response assemblyをResponse Composerへ移し、会話文と構造化blockを分離する。
3. proposalからRuntime step列を作るPlan型と、専用Plan Executorを抽出する。
4. Photo連携をTravel / Photo双方のAdapter境界を通して追加する。
5. 更新ToolをRuntime確認付きPending Actionへ接続する。
