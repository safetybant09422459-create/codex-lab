# Decision: Jarvis Core LLM Contract

## 日付

2026-07-05

## Status

Accepted（目標Architecture。現行実装は未対応）

## 背景

[Turn Contract / Single Agent Loop](2026-07-turn-contract-single-agent-loop.md)は、全Channelが一つのAgent
LoopとTurn Contractを共有することを決めた。[Domain Provider Contract](../provider_contract.md)は、Coreが
利用できるOperationとRuntimeへの接続を定めた。しかし、CoreがLLMへ渡す入力とLLMから受け取る出力を固定しない
まま実装すると、Chat、Voice、Camera、Developer、Travelごとに独自prompt、独自JSON、会話継続判定が増え、
Pythonの第二の頭脳が再発する。

本Decisionは、Turn ContractのうちLLM境界だけを具体化する。LLMの内部思考は契約対象にせず、Coreが扱うのは
検証可能な入力contextと、外部化されたActionだけである。

## 決定

Jarvis Coreは、Channel、Skill、Domain Providerに依存しない一つのLLM Contractを持つ。すべてのLLM呼び出しは
共通入力を受け取り、次のActionを必ず一つだけ返す。

* `answer`
* `ask_clarification`
* `call_operation`
* `request_confirmation`
* `refuse`

Channel adapterは媒体を決定的に正規化し、Actionの意味を変えず表示・読み上げ等へ変換する。Domain Providerは
Action形式を定義しない。AI Model Provider adapterは各社APIのtool callやstructured outputをこの契約へ変換するが、
意味判断を追加しない。

Pythonは入力を組み立て、LLM出力をschema validationし、選択済みOperationをRuntimeへ渡し、保存状態を管理する。
ユーザー意図、Provider、Operation、会話継続、話題転換を分類または推測しない。

## LLM入力

LLM入力は論理契約であり、特定AI Model Providerのwire formatや、全項目の永続化を要求しない。Coreは目的、権限、
token budgetに必要な範囲だけを渡し、欠落項目は欠落として明示する。

| field | 所有者 | 意味 |
| --- | --- | --- |
| `contract_version` | Core | LLM Contractのversion |
| `turn_id` | Core | 現在turnの追跡ID |
| `session_id` | Core | 会話状態を関連付けるID。認可の証拠ではない |
| `principal` | 認証境界 | 検証済み主体の必要最小限のview。自己申告値を使わない |
| `channel` | Channel adapter | 媒体と表現上の制約。意味分類や権限を含めない |
| `normalized_input` | Channel adapter | text、transcript、attachment refs、locale等。intentやtopic labelを加えない |
| `conversation_context` | Core | budget内の直近turnとsanitized summary |
| `conversation_state` | Core | 前turnまでに確定・保留された作業状態 |
| `persona_context` | Core / Memory | Jarvisの価値観、対話姿勢、応答制約 |
| `memory_context` | Memory境界 | purposeとvisibilityを適用した許可済み生活文脈 |
| `activation_candidates` | Activation RAG | 未検証の候補。Evidence、認可、確定argumentsではない |
| `available_operations` | Operation Catalog / Runtime | 提示可能なOperationのLLM向けview。実行許可ではない |
| `runtime_policy` | Runtime | budget、risk、confirmation、開示等の機械検証可能な制約 |
| `prior_observations` | Runtime | 成功、拒否、確認待ち、validation error等の構造化結果 |

`principal`、Memory、候補、ObservationはLLMへ無制限に渡さない。秘密、不要な家族情報、生画像・音声、Repository
全件、監査ログ本文は参照または最小化されたviewにする。`available_operations`はProvider Operation Catalogから
生成し、Channel別・Skill別の手書きallowlistを別の正本にしない。

### Conversation State

Coreは少なくとも次を保持できる。これはPythonが分類したstateではなく、前回までの検証済み結果、Runtime-owned
pending state、LLMが外部化してschema validationされた更新を合わせたserver-owned stateである。

```json
{
  "current_topic": null,
  "previous_topic": null,
  "active_entities": [],
  "pending_question": null,
  "unresolved_intent": null,
  "last_operations": [],
  "pending_confirmation": null
}
```

LLMは現在入力とこのstateを見て、前の話の続き、話題転換、確認への返答、新規依頼、未解決意図の継続、会話終了を
判断する。その外部化された判断はAction内の`conversation_update.transition`に次のいずれかで表す。

* `continue_topic`
* `switch_topic`
* `answer_pending_question`
* `respond_to_confirmation`
* `start_request`
* `continue_unresolved_intent`
* `end_conversation`

`conversation_update`は`current_topic`、`previous_topic`、`active_entities`、`pending_question`、
`unresolved_intent`の更新案を持てる。Coreはshape、size、参照整合性を検証して保存するだけで、文言からtransitionを
再分類しない。`last_operations`はRuntime結果から、`pending_confirmation`はRuntimeが発行した不変snapshotから更新し、
LLMに捏造、改変、解除させない。

`current_topic`等は短い自然言語の作業要約または安定参照であり、Skill IDの強制分類ではない。stateは会話を再開する
補助であって、認可、Evidence、Domain Entityの正本ではない。会話終了時も保持・削除policyはCoreが決定的に適用する。

## LLM出力

出力は一つのAction objectであり、共通envelopeは次を持つ。

```json
{
  "contract_version": "1",
  "action": "answer",
  "message": "ユーザーへ返す内容",
  "conversation_update": {
    "transition": "continue_topic"
  }
}
```

共通fieldは次のとおりとする。

| field | 必須 | 意味 |
| --- | --- | --- |
| `contract_version` | yes | Coreが受理可能な契約version |
| `action` | yes | 5種類の排他的Actionの一つ |
| `message` | actionによる | ユーザーに提示可能な外部化された内容 |
| `conversation_update` | yes | 会話遷移とstate更新案。内部思考や理由の記録欄ではない |

Action別の追加契約は次のとおりとする。

| action | 必須field | 意味 |
| --- | --- | --- |
| `answer` | `message` | 現在contextとObservationで回答する |
| `ask_clarification` | `message` | 不足情報を一つの明確な質問として返す |
| `call_operation` | `provider_id`, `operation_id`, `arguments` | Catalog中のOperation実行をRuntimeへ提案する |
| `request_confirmation` | `message` | Runtimeが返した確認待ち内容を提示する。確認要否を確定しない |
| `refuse` | `message` | 安全、権限、能力、方針上の拒否と可能なら代替を返す |

`call_operation`の最小形は次のとおりである。

```json
{
  "contract_version": "1",
  "action": "call_operation",
  "provider_id": "travel",
  "operation_id": "get_trip",
  "arguments": {"trip_id": "trip-1"},
  "conversation_update": {
    "transition": "continue_unresolved_intent"
  }
}
```

Action schemaは判別共用体として定義し、未知field、複数Actionのfield混在、自然文だけのoperation call、不明な
`provider_id` / `operation_id`、schema不適合argumentsを拒否する。validation失敗時にPythonが内容を補正、推測、
別Actionへ変換してはならない。失敗は安全に実行を止め、機械的なretry policyの範囲で同じ契約を再要求するか、
構造化errorとして扱う。

### Confirmation

確認への返答かどうかの意味判断はLLMが行い、`conversation_update.transition`を
`respond_to_confirmation`として、対応する`call_operation`または確認を求め直すActionを返す。ただし実行可否は
Runtimeが所有する。Runtimeは保存済み`pending_confirmation`のprovider、operation、arguments、principal、期限、
policyとの完全一致を検証し、一致しなければ実行しない。LLMの「確認済み」という主張や、session IDだけを承認の
証拠にしない。

`request_confirmation`は、原則としてRuntimeが`confirmation_required` Observationを返した後にだけ使う。
LLMが先に安全上の確認が必要と判断して提案することはできるが、確認tokenの発行、pending snapshotの保存、確認要否の
確定はRuntimeが行う。

## 内部思考を扱わない

LLM Contractはreasoning、rationale、analysis、scratchpad、hidden thought、chain-of-thoughtを要求しない。
保存、監査、debug、学習eventにもこれらのfieldを設けない。必要な説明はユーザー向け`message`、選択されたAction、
Operation参照、Observation provenance、sanitized trace refsから構成する。

AI Model Providerが内部的なreasoning tokenや独自fieldを返しても、adapterはJarvis Coreの契約へ取り込まない。
運用上必要なmodel名、latency、token使用量、schema error等の機械metadataは、Actionとは別のsanitized telemetryとして
扱える。

## Turn Contract / Provider Contract / Runtimeとの関係

| 契約 | 範囲 | 入出力 |
| --- | --- | --- |
| Turn Contract | Channel入力からChannel応答までの1ターン全体 | LLM呼び出し、Runtime反復、Observation、最終応答を包含 |
| LLM Contract | Turn内のLLM判断境界 | 共通contextを受け、5種類のActionを一つ返す |
| Domain Provider Contract | 利用可能な能力と1 Operationの決定的実行 | Catalogと構造化arguments / result |
| Runtime contract | Action提案から安全な実行とObservation化 | validation、permission、confirmation、audit、dispatch |

LLM Contractの`available_operations`はProvider ContractのOperation Catalogのviewであり、
`call_operation`は`provider_id + operation_id + arguments`でProvider Contractへ接続する。Runtimeはそれを提案として
受け取り、安全gateを通した結果を`prior_observations`として同じLLM Contractへ戻す。LLM ActionはPermission、
Confirmation、Audit、Repositoryの正本性を代替しない。

## 禁止する設計

* Pythonによるユーザー意図分類、Provider選択、ユーザー意図ベースのOperation選択
* Pythonによる会話継続、話題転換、確認返答、新規依頼、会話終了の分類
* `TopicRouter`、`ConversationStateClassifier`、Skill別会話継続判定
* Channel別、Provider別、Skill別のLLM出力schemaまたはAgent Loop
* Travel専用plan / JSONを共通Loopの前提にすること
* PythonによるLLM Actionの意味的修復、固定回答、Response Composer
* hidden thought / chain-of-thoughtの要求、保存、監査、表示
* Activation候補やconversation stateをEvidence、認可、Domain Entityの正本として使うこと
* LLM ActionからRuntimeを迂回してProvider、Repository、外部APIを呼ぶこと

決定的な入力正規化、schema validation、Catalogの厳密一致、stateのsize / version管理、permission、confirmation、
audit、redaction、timeout、retry、telemetryはPythonの責務としてよい。自然言語の意味を判断しないことが条件である。

## 将来実装時の移行方針

1. 本Decisionからversion付きinput schemaと5 Actionの判別共用体schemaを定義し、valid / invalid fixtureを作る。
2. 現行Chat APIをChannel adapterとして共通入力へ変換し、公開response互換は境界adapterだけで維持する。
3. Core-owned conversation state storeを導入し、Runtime-owned fieldとLLM更新可能fieldを分離する。
4. 単一LLM callで`answer`、`ask_clarification`、`refuse`と会話遷移を接続し、topic classifierを追加しない。
5. Operation Catalogを`available_operations`へ投影し、read-only `call_operation`をRuntime経由で接続する。
6. Runtime Observationを同じLoopへ戻し、budget内の反復と最終`answer`を接続する。
7. pending confirmationの不変snapshot、期限、再開検証を実装してからwrite / actionを接続する。
8. Web / Chatのcontract test後、Voice、Camera、Developer等を同じ契約のChannel adapterとして追加する。
9. 移行済み経路から旧Router、Planner、独自JSON、Skill別state判定、固定回答を削除する。

移行中も複数の正本schemaを作らない。旧公開responseが必要な期間は、共通Actionから表示形式へ機械的に変換する
compatibility adapterとして隔離し、新規ChannelやProviderへコピーしない。

## 再検討条件

共通Contractでは表せないActionが複数Channelの代表use caseで必要と実証された場合、またはversioned schemaの
latency、cost、reliabilityがbenchmarkで許容範囲を満たさない場合に再検討する。Channel / Provider固有schemaや
Pythonの意味分類を先に追加せず、共通Actionのversion追加、context view、AI Model Provider adapterを検討する。

## Jarvis Principle Check

1. Web UIから利用できるか: WebをChannel adapterとして同じLLM Contractへ接続できる。
2. API / Toolとして利用できるか: Core APIは共通Actionを扱い、OperationはRuntime / Provider Toolへ接続できる。
3. 将来MCP Tool化できるか: MCP Operationも同じCatalogとRuntimeを使い、独自LLM schemaを必要としない。
4. Jarvis Coreから呼び出せるか: 本契約はJarvis Coreの単一Agent Loopが所有するLLM境界である。
5. UI依存のロジックになっていないか: Channelは正規化と提示だけを担い、意味判断はLLMへ置く。
6. 読み取り系か更新系か: 契約自体は状態管理で、read / write Operationの実行はRuntimeが制御する。
7. 副作用・権限・プライバシー上の注意はあるか: 最小context、Runtime gate、確認snapshot、監査、redactionを必須にする。
