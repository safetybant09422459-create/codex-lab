# Decision: Chat Core Skill Adapter Architecture

## 日付

2026-06

---

## 背景

Jarvis Home、Chat API、Runtime接続、multi-step、deep link、conversation contextが実装され、
Chat Core v0.2 Foundationでは`EntityRef`、`ConversationState`、`ChatResponseV1`と
`TravelChatAdapter`の土台が追加された。

このままEntity Resolver、Response Composer、Photo連携、Pending Actionを個別に足すと、
Chat CoreがSkill固有の検索規則、Tool分岐、表示整形を抱え、Skill追加のたびに変更が必要になる。
また、Tool結果をそのまま返すだけでは、ユーザーがTool名やSkill境界を理解しなければならず、
Jarvisが目指す自然な会話にならない。

---

## 決定

Jarvis Chatの目標を「Skill接続」ではなく「Skill連携」とする。

Chat Coreは、意図補完、Conversation State、候補探索の調停、計画、Runtime接続、応答契約という
共通ライフサイクルを持つ。Skill固有のEntity解決と入出力変換はChat Skill Adapterへ委譲する。
Skillが増えても、CoreへSkill名やTool IDによる分岐を増やさない。

```text
Chat entry point
      ↓
Chat Core common protocols
      ├ ConversationState / EntityRef
      ├ EntityResolver / EntityCandidate
      ├ Plan / Execute
      └ ChatResponseV1
      ↓
Chat Skill Adapter
      ↓
Runtime safety boundary
      ↓
SkillExecutor / SkillRepository
```

Chat Skill Adapterは次を担当する。

* Skill固有Entityの候補検索、正規化、順位付け
* Skill固有slotと`EntityRef`の変換
* Runtime / Tool結果から`content_blocks`への変換
* Skillに適した`suggested_actions`候補の組み立て

Chat CoreはAdapterの登録と共通Protocolだけを知り、Travel、Photoなどの検索詳細を持たない。
Chat Skill AdapterはExternal AdapterやSkillExecutorを置き換えず、会話境界に限定する。

---

## 入力とEntity Resolution

ユーザー発話は曖昧で不完全であることを前提にする。「神戸旅行」という作業文脈から
「須磨シーワールド」のような候補を探す処理を、単純なTool引数不足として終わらせない。

Entity ResolutionはSkill横断で使う共通概念とし、Coreは解決要求、候補、曖昧性を共通形式で
扱う。一方、候補の取得元、検索規則、正規化、Skill内の意味判断はChat Skill Adapterが
担当する。候補探索は認可ではないため、Entityの利用前にはserver-sideで実在とアクセス権を
検証する。複数候補を根拠なく自動選択しない。

---

## 出力とResponse Composer

Tool結果をそのままUIへ返さない。Response Composerは実行結果とConversation Stateを、
人間向けの`message`、UI非依存の`content_blocks`、安全な`suggested_actions`へ変換する。

「2日目は？」に対してtimeline JSONを露出するのではなく、現在のTripと対象日を踏まえた
会話文を返し、必要な構造化内容を添える。DOM、画面固有component、任意のnavigation URLは
Composerの正規出力にしない。

---

## Conversation State

Conversation Stateは会話中の作業状態であり、長期Memoryではない。現在のTrip、写真、予定、
候補を`EntityRef`として参照し、Entityの出所と検証時刻を保持する。SkillのEntity本体は各Skillが
所有し、Preferenceや長期的な思い出はMemoryが扱う。

クライアントから受け取るcontextは未信頼ヒントとし、実在、認可、server-side状態の証明に
使わない。現在の互換contextから、将来は認証済み主体に紐づくserver-owned
`conversation_id`へ移行する。

---

## 安全境界

* BrowserからOpenAI APIを直接呼ばない。
* LLMからRuntime、Executor、Repositoryを直接呼ばない。
* LLMに`role`、`confirmed`、Permission、navigation URLを決定させない。
* CoreはLLM提案を検証し、実行はRuntimeへ委譲する。
* RuntimeがPermission、Confirmation、Auditを担当する。
* 更新操作は検証済みPending Actionと人間確認を経てから実行する。

---

## 実装方針

一度に汎用基盤を完成させず、まず一つの会話ユースケースを縦に薄く動かす。動作から見えた
責務の歪みをdocsとProtocolへ反映する。CoreにSkill固有分岐を追加したくなった時点で、
Adapterまたは共通契約の不足を見直す。

設計は「その機能を作れるか」ではなく、「Skillが増えてもCoreを肥大化させず育てられるか」で
判断する。

---

## 影響

良い影響:

* ユーザーがTool名やSkill境界を意識せずに済む
* Skill追加時のChat Core変更を抑えられる
* Web UI、API、将来のMCPや音声で同じ応答契約を再利用できる
* 未信頼context、LLM提案、Runtime実行の信頼境界が明確になる

注意点:

* Adapterが単なる巨大なSkill別Orchestratorにならないよう責務を限定する
* 共通化を急ぎすぎず、複数の縦切りで確認できた概念だけをCore Protocolへ上げる
* `ChatResponseV1`は現時点では内部契約であり、公開Chat APIは互換形式を維持する
* Entity Resolver、汎用Response Composer、server-owned conversationはFoundation後の未実装項目である

---

## 関連Decision

* [Skill Standard Architecture](2026-06-skill-standard-architecture.md)
* [Travel Experience Architecture](2026-06-travel-experience-architecture.md)
* [Travel / Photo Separation](2026-06-travel-photo-separation.md)

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。Web UIはChat APIから`message`とUI非依存の構造化内容を受け取る。
2. API / Toolとして利用できるか
   * 利用できる。Chat CoreとSkill AdapterはUIに依存せず、Runtime Tool境界へ接続する。
3. 将来MCP Tool化できるか
   * できる。共通のEntity参照と応答契約をMCP Handlerから再利用できる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。この決定自体がJarvis CoreからSkill群を連携するための境界を定める。
5. UI依存のロジックになっていないか
   * なっていない。ComposerはDOMではなく`message`、`content_blocks`、`suggested_actions`を返す。
6. 読み取り系か更新系か
   * 両方へ適用する。まず読み取り系を縦に通し、更新系はPending ActionとRuntime確認を必須にする。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。会話context、Trip、位置、写真はプライバシー対象であり、client contextとLLM出力を信頼せず、更新はPermission / Confirmation / Auditを通す。
