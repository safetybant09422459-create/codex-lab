# Decision: Turn Contract / Single Agent Loop

## 日付

2026-07-05

## Status

Accepted（目標Architecture。現行実装は段階移行中）

## 背景

Jarvisは個人・家族向け生活OSとして、Chat、Voice、Camera、Notification、Developer、Travelなど複数の
ChannelとSkillを扱う。入口や能力ごとにAgent Loop、Router、Planner、Answer Generatorを作ると、意味判断が
分散し、Pythonがユーザー意図やProvider選択を再判定する第二の頭脳が再発する。

[Jarvis vNext Responsibility Architecture](2026-07-vnext-single-agent-loop-architecture.md)は意味判断を単一の
LLM Agent Loopへ集約する責務境界を採用した。本Decisionはその判断を変更せず、Jarvis Coreが全Channelで共有する
1ターンのデータ契約、反復、Runtimeとの制御境界を具体化する。

Turn内でLLMへ渡す入力と、LLMが返すActionの詳細は
[Jarvis Core LLM Contract](2026-07-llm-contract.md)が定める。

## 決定

Jarvis Coreに、Channel、Skill、Domain Providerを横断して共有するAgent Loopを一つだけ置く。各Channelは入力を
共通Turnへ正規化し、最終応答、確認要求、進捗を媒体に合わせて表現する。各Domain ProviderはOperation Catalogで
能力を公開し、選択済みOperationを決定的に実行する。どちらも独自のAgent Loopを持たない。

LLM Agent Loopは、利用可能なOperation、Memory、Persona、Activation候補、Runtime policy、これまでの
Observationを見て次のactionを決める。RuntimeはactionとOperation callを検証し、Permission、Confirmation、
Audit、budget、実行を担当する。Provider結果はObservationとして同じLoopへ戻し、最終回答はLLMが生成する。

```text
Channel input
  -> normalize Turn input
  -> Jarvis Core / single LLM Agent Loop
       -> answer / ask_clarification / refuse
       -> call_operation
            -> Runtime safety boundary
                 -> Domain Provider Operation
                 -> Observation
            -> same LLM Agent Loop
       -> final_response
  -> Channel presentation
```

この「一つ」は同時に一turnしか処理できない単一processや単一model instanceを意味しない。複数sessionとturnは
並行実行できるが、すべて同じTurn Contractと責務境界を使う。model routing、context縮小、LLM sub-loopが将来
必要になっても、Jarvis Core内の実装詳細とし、Channel、Provider、Skill固有の別の頭脳にはしない。

## Turn Contract

Turn Contractはtransportや保存形式を固定するschemaではなく、Jarvis Core内で欠かしてはならない論理契約である。
実装時はrequest、server-owned state、LLM action、Runtime outcome、responseへ分割できる。すべてをLLMへ渡したり、
すべてを永続化したりしてはならない。

| 要素 | 所有者 / 生成元 | 契約上の意味 |
| --- | --- | --- |
| `turn_id` | Core / Runtime | 1回の要求を追跡する一意ID。確認後の再開でも元turnとの関連を保持する |
| `session_id` | Core / Runtime | Channelをまたいで会話状態を関連付けるID。認可の証拠にはしない |
| `principal` | 認証境界 / Runtime | user、family、role、scope等の検証済み主体。ChannelやLLMに自己申告させない |
| `channel` | Channel | `chat`、`voice`、`camera`、`notification`等の媒体情報。意味判断や権限を内包しない |
| `user_input` | Channel | ユーザーが提供した原入力または安全な参照。音声・画像等の巨大データを無条件に複製しない |
| `normalized_input` | Channel | transcript、text、attachment refs、locale等の決定的な共通表現。意図分類結果を入れない |
| `available_operations` | Operation Catalog / Runtime | principalと実装状態に応じて提示可能なOperation。選択や実行許可そのものではない |
| `memory_context` | Memory境界 | purposeとvisibilityを適用した生活文脈。Domain Repositoryの正本を複製しない |
| `activation_candidates` | Activation RAG | 未検証のEntity候補。Evidence、認可、確定argumentsとして扱わない |
| `persona_context` | Core / Memory | Jarvisの価値観、対話姿勢、応答制約。Permissionや事実を上書きしない |
| `runtime_policy` | Runtime | action種別、risk、budget、timeout、confirmation等の機械検証可能な制約 |
| `llm_action` | LLM Agent Loop | 次に回答、質問、Operation提案、確認提示、拒否のどれを行うかという構造化出力 |
| `operation_call` | LLM Agent Loop | 選択した`provider_id`、`operation_id`、`arguments`。Runtime検証前は提案である |
| `observation` | Runtime | 実行結果、拒否、確認待ち、errorをLoopへ戻す構造化結果 |
| `final_response` | LLM Agent Loop | Observationと制約を評価して生成した最終的な意味内容 |
| `trace_refs` / `audit_refs` | Core / Runtime | sanitized traceと監査記録への参照。生の思考過程や秘密を含めない |

`user_input`と`normalized_input`を分ける理由は、媒体変換と意味判断を分離するためである。例えばVoice Channelは
音声をtranscriptと参照へ変換できるが、「Travelを使う要求」と分類しない。Camera Channelも画像参照と取得時刻を
正規化できるが、画像の意味からOperationを決定しない。

### LLM Action

`llm_action`は少なくとも次の排他的なaction種別を持つ。

| action | 意味 | 次の処理 |
| --- | --- | --- |
| `answer` | Operation不要、またはObservationが十分 | LLMが`final_response`を生成する |
| `ask_clarification` | 安全に判断するための情報が不足 | 質問を`final_response`として返しturnを終了する |
| `call_operation` | 構造化Operationの実行を提案 | Runtimeへ`operation_call`を渡す |
| `request_confirmation` | ユーザーへ実行内容の確認提示が必要 | Runtimeが算出した確認内容を提示する。LLMの提案だけで確認要否を確定しない |
| `refuse` | 安全、権限、能力、方針上応じられない | 理由と可能な代替をLLMが生成する |

LLMは`request_confirmation`を提案できるが、Confirmationの要否、対象arguments、pending state、確認tokenの
発行と検証はRuntimeが所有する。LLMが`call_operation`を選んでもRuntimeが確認必須と判定した場合、実行せず
`confirmation_required` Observationを返す。LLMが確認不要と判断してもRuntime policyを迂回できない。

### Operation Call

```json
{
  "provider_id": "travel",
  "operation_id": "get_trip",
  "arguments": {"trip_id": "trip-1"}
}
```

Operation callは自然文やSkill固有planではなく、[Domain Provider Contract](../provider_contract.md)の
`provider_id + operation_id + arguments`へ接続する。LLMがCatalogから選択し、RuntimeがCatalogの実装状態、
schema、principal、permission、confirmation、risk、budgetに照らして検証する。Provider Registryは厳密一致で
解決するだけで、曖昧な入力からProviderやOperationを推測しない。

### Observation

Observationは成功結果だけでなく、確認待ち、拒否、validation error、timeout、Provider errorも同じLoopへ戻す。
最低限、次の信頼情報を保持できるようにする。

```json
{
  "result": {},
  "provenance": {
    "provider_id": "travel",
    "operation_id": "get_trip",
    "source_refs": []
  },
  "visibility": "family",
  "limitations": []
}
```

`provenance`は正本または外部sourceへの追跡情報、`visibility`は回答・後続処理への開示範囲、`limitations`は
freshness、不完全性、stub、planned、redaction等の制約を表す。値が不明なら`unknown`または明示的な欠落として
扱い、Pythonが意味推論で補完しない。ObservationはProviderの会話文ではなく、LLMが評価できる構造化結果とする。

## 1ターンの遷移

1. Channelが原入力を取得し、`normalized_input`へ決定的に変換する。
2. Core / Runtimeが`turn_id`、`session_id`、検証済み`principal`、`runtime_policy`を設定する。
3. CoreがOperation Catalog、許可されたMemory / Persona、任意のActivation候補を組み立てる。
4. LLM Agent Loopが`llm_action`を一つ生成する。
5. `call_operation`ならRuntimeが検証する。拒否または確認待ちはObservationとして返し、許可時だけProviderを実行する。
6. Runtimeが結果とprovenance、visibility、limitations、trace / audit refsをObservationにする。
7. LLM Agent LoopがObservationの十分性を評価し、必要ならbudget内で4から6を反復する。
8. LLMが`final_response`を生成し、Channelが意味を変えず媒体固有形式へ変換する。

Clarificationは会話上の不足を埋める新しいturnである。ConfirmationはRuntime-owned pending operationを再開する
安全手続きであり、同じものではない。確認への返答という意味判断はLLMが行うが、確認後は保存済みのprovider、
operation、arguments、principal、policyとの一致をRuntimeが検証する。LLMの判断やユーザーの「はい」だけを
実行許可にしない。

Runtimeは最大Operation回数、token / time budget、timeout、cancellation、retry、idempotencyを強制する。
budget超過や回復不能errorはObservationとしてLoopへ返し、Pythonで固定の最終回答を組み立てない。

## Provider Contractとの関係

Turn ContractとDomain Provider Contractは置換関係ではない。

| 契約 | 範囲 | 判断すること | 判断しないこと |
| --- | --- | --- | --- |
| Turn Contract | Channel入力から最終応答までの1ターン | LLMによる意図理解、Operation選択、結果評価、質問、回答 | Provider内部実装、認可の確定 |
| Domain Provider Contract | Catalog公開と1 Operationの実行 | 決定的なCRUD、検索、外部API、ドメイン不変条件 | ユーザー意図、会話、Provider選択、最終回答 |
| Runtime contract | Operation提案から安全な実行・Observation化まで | schema、permission、confirmation、audit、budget、dispatch | 自然言語の意味、回答内容 |

`available_operations`はProvider Operation CatalogのLLM向けviewであり、別のCapability Catalogを手入力で
二重管理しない。安全metadataの正本は既存Tool JSONに残る。Provider固有resultはObservationの`result`へ入り、
共通のprovenance、visibility、limitationsはRuntimeが欠落を明示しながらenvelope化する。

## 禁止するArchitecture

* Chat、Voice、Camera、Notification等、ChannelごとのAgent Loop
* Travel、Developer、Home等、ProviderまたはSkillごとのAgent Loop / Planner
* Pythonのkeyword、正規表現、score、固定ルールによるユーザー意図分類
* Pythonによる会話上のProvider選択
* Pythonによるユーザー意図ベースのOperation選択やarguments推測
* Providerが返す自然文をそのままJarvisの最終回答にすること
* Python template、fallback文、Response Composerによる最終回答生成
* Activation候補を正本、認可、Evidence、確定argumentsとして利用すること
* Channel、Provider、SkillからRuntimeを迂回してOperationを実行すること

決定的な媒体変換、schema validation、IDの厳密解決、permission、confirmation、redaction、error codeの生成は
禁止対象ではない。これらは自然言語の意味を判断しない限りPythonの責務である。

## 移行方針

1. Turn Contractのcharacterization testを先に定義し、Chatのread-only代表turnを最初の縦断経路にする。
2. 現行Chat requestを共通入力へadapterし、公開API互換を保ったまま`turn_id`、`session_id`、principalをserver-ownedにする。
3. Provider Operation Catalogからprincipalに提示可能な`available_operations` viewを生成し、別metadataを作らない。
4. 単一LLM callに構造化`llm_action`を導入し、まず`answer`、`ask_clarification`、`refuse`を移す。
5. read-only OperationをRuntime経由で接続し、Provider結果をprovenance付きObservationとしてLoopへ戻す。
6. loop budget、timeout、error、traceを追加し、複数Operationの反復を許可する。
7. Runtime-owned confirmation再開契約を導入してからwrite / actionを接続する。
8. Web / Chatで契約を検証後、Voice、Camera、Notificationを同じ入力adapterとして追加する。
9. 利用経路が移った単位で旧Router、Planner、Skill別分岐、固定回答を削除する。

各段階で、Runtime safety gateの迂回、候補の事実化、principal / visibilityの漏えい、Provider自然文の最終回答化、
Channel固有判断の追加があれば次へ進まない。現行のToolなしBasic Chatは移行中の機能低下であり、別Loopを作る
理由にはしない。

## 既存Decisionへの影響

本Decisionは[Jarvis vNext Responsibility Architecture](2026-07-vnext-single-agent-loop-architecture.md)を
置き換えず、その単一Agent Loopとstateの判断をTurn Contractとして具体化する。

[Domain Provider Responsibility Boundary](2026-07-domain-provider-boundary.md)のProvider責務も維持する。
Provider Operation Catalogは`available_operations`、選択済みOperationは`operation_call`、Providerのstructured
resultはRuntime envelopeを通して`observation.result`へ対応する。

## 再検討条件

共通Turn Contractでは満たせないlatency、cost、reliability、安全性が代表benchmarkで測定された場合に再検討する。
その場合もChannel / Skill / Provider固有Loopを先に導入せず、context縮小、model routing、非同期継続、LLM
sub-loopをJarvis Core内部で検討する。Pythonへの自然言語判断の移管は代替案にしない。

## Jarvis Principle Check

1. Web UIから利用できるか: Web / ChatをChannel adapterとして同じTurn Contractへ接続できる。
2. API / Toolとして利用できるか: Core APIはTurn Contract、Tool実行はRuntime / Provider Contractとして公開できる。
3. 将来MCP Tool化できるか: MCP Operationも同じCatalogとRuntimeを使え、MCP自体を別Loopにしない。
4. Jarvis Coreから呼び出せるか: 本DecisionはJarvis Coreが所有する共通の1ターン契約である。
5. UI依存のロジックになっていないか: Channelは入力正規化と出力表現だけを担う。
6. 読み取り系か更新系か: Turn Contractは両方を扱い、write / actionはRuntime confirmation後だけ実行する。
7. 副作用・権限・プライバシー上の注意はあるか: principal、visibility、最小開示、確認、監査、redaction、trace参照をRuntimeで強制する。
