# Chat Core v0.2 Foundation

Chat Core v0.2 Foundationは、Chatの賢さや対応Toolを増やす変更ではない。
Entity Resolution、Response Composer、Photo連携、Pending Actionを追加する前に、
`chat_orchestrator.py`へ集まり始めた責務を分離するための内部契約を定義する。

## 4層の責務

1. Conversation State
   - `ConversationState`が現在のSkill、選択Entity、Skill固有slotを保持する。
   - Entityは`EntityRef`で表し、出所と検証時刻を区別する。
2. Entity Resolution
   - `EntityResolver` Protocolと`EntityCandidate`を共通入口にする。
   - v0.2では候補型と境界だけを定義し、曖昧検索や自動選択は追加しない。
3. Plan / Execute
   - 現在のproposal検証、bounded loop、Chat Tool Policy、Runtime実行を維持する。
   - Chat / LLMはExecutorやRepositoryへ直接到達せず、Runtimeを迂回しない。
4. Response Composer
   - `ChatResponseV1`、`ContentBlock`、`SuggestedAction`を内部応答契約とする。
   - `legacy_chat_response_to_v1()`とTravel用Composerで段階移行できる。

## Travel adapterとcontext信頼境界

`travel_chat_adapter.py`は、legacy contextとConversation Stateの相互変換、Trip
`EntityRef`生成、Travel content block生成を担当する。

Browserから受け取る`selected_trip_id` / `selected_trip_title`は互換維持のため残すが、
信頼済み状態ではなく`source=client_context_hint`、`verified_at=None`の未信頼ヒントへ
変換する。これらはEntityの実在やアクセス権を証明しない。特に選択旅行の日程取得では、
従来通りRuntimeの`get_trip`を先に実行して実在確認する。Runtime結果から作るEntityだけが
`source=travel_runtime`と`verified_at`を持つ。

## API互換とrole

`POST /api/chat`は当面、既存の`action`、`tool_id`、`arguments`、`result`、
`navigation`、`updated_context`、`debug`を返す。UIの変更は不要で、内部契約への変換は
追加したComposerで行える。`ChatResponseV1`を公開APIへ切り替えるのは別フェーズとする。

ChatのroleはBrowserやLLMが所有しない。互換性のためrequestの`role`フィールドは受理するが
無視し、認証実装まで`/api/chat`はserver側の暫定`admin`をRuntimeへ渡す。
認証導入時は、固定値を認証済みsession/principalから導出する値へ置き換える。

## 次の抽出候補

- Entity Resolver実装と候補選択policy
- proposalからRuntime step列を作るPlan型
- bounded loopを専用Plan Executorへ移動
- legacy response assemblyをResponse Composerへ移動
- 更新Toolを確認付きPending Actionへ接続

