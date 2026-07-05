# Decision: Conversation Quality / Python Brain Regression Guard

## 日付

2026-07-06

## Status

Accepted

## 背景

Jarvis ChatはAgent Host、LLM、Runtime、Domain Provider、Observation、Conversation State v0を使う経路を
持ち始めた。今後Conversation Quality Testの評価を改善するとき、個別ケースを通すためのkeyword分岐、話題判定、
Provider選択、固定fallback回答をPythonへ追加すると、LLM Agent Loopとは別の「Python Brain」が再発する。

これは短期的に点数を上げても、言い換えや複数Turnに弱く、Channel / Skillごとに意味判断を分散させる。
また、Catalog、Provider、Conversation Stateを宣言・事実・状態の境界ではなくrouting ruleとして使わせてしまう。

## 決定

**Conversation quality improves by improving context, observations, provider contracts, catalog descriptions, and memory —
not by adding Python intent logic.**

「会話力を上げる」とはPythonを賢くすることではない。LLMが文脈を維持し、必要なOperationを選び、不足時に
確認し、根拠のある自然な回答を作れるように、判断材料と契約を改善することである。LLM Contractと単一Agent Loopを
維持し、Pythonは決定的な実行基盤に限定する。

## Improvement Target Principle

Jarvisの会話品質改善では、改善対象を明確に区別する。

改善対象は次である。

* Context Assembly
* Conversation State
* Observation
* Provider Contract
* Capability Description
* Operation Description
* Catalog metadata
* Memory Provider
* Prompt
* LLM Contract

これらはLLMが判断しやすくなるための「材料」である。

一方、次を改善対象にしてはならない。

* Pythonによる意図分類
* Pythonによる話題継続判定
* Pythonによる話題転換判定
* PythonによるProvider選択
* PythonによるOperation選択
* PythonによるClarification生成
* PythonによるConversation Quality Test専用分岐
* Python fallback回答
* Keyword Router
* Topic Router
* ConversationStateClassifier

改善の目的は「Pythonを賢くすること」ではなく、「LLMがより賢く判断できる材料を提供すること」である。

レビューでは必ず、この変更が「LLMへの入力・材料の改善」か、それとも「LLMの代わりをPythonが始めている」
のかを確認する。後者なら設計違反として扱う。

## 会話力を上げる正しい方法

* Conversation Contextの構成、順序、明瞭さを改善する。
* token budget内で必要なprior turnsとlast observationsを適切に渡す。
* Observationのprovenance、visibility、limitations、freshnessを明示する。
* Provider Operationのdescription、input / output schema、examples、limitationsを改善する。
* Capability説明を内部実装名ではなくユーザーが理解できる能力として改善する。
* Memory Providerから、認可・visibility・retentionを守った生活文脈を提供する。
* LLMのsystem / developer promptを改善する。
* [Jarvis Core LLM Contract](2026-07-llm-contract.md)を守り、判断を構造化Actionとして外部化する。

CatalogのdescriptionやexamplesはLLMへの材料であり、Pythonが発話と照合するruleではない。MemoryとConversation
Stateも文脈であり、Evidence、認可、Domain Entityの正本、Python routingの入力にはしない。

## Pythonが担ってよいこと

Pythonは自然言語の意味を解釈せず、次の決定的処理を担える。

* 会話履歴を保存し、`session_id`で分離する。
* 明文化されたtoken / item budgetに従って履歴とObservationを決定的に切り詰める。
* principal、permission、visibilityに従って候補と文脈をfilterする。
* Runtimeのvalidation、permission、confirmation、audit、timeout等のsafetyを守る。
* LLMが選択したProvider OperationをRuntime経由で実行する。
* Provider結果をprovenance等を持つObservationへ構造化する。
* schema、version、size、参照整合性をvalidationする。

切り詰めやfilterはpolicyと構造化metadataに基づく。同じ処理を、話題らしさ、keyword、過去Provider等の
意味scoreによる選択へ変えてはならない。

## Pythonが担ってはいけないこと

次を禁止する。

* `if "それ" in message`、`if "写真" in message`、`if "旅行" in message`のような自然言語keyword分岐。
* `if previous_provider == "travel"`のように過去のProviderから現在の意味を確定する分岐。
* Pythonによる話題継続、話題転換、参照解決、Provider選択、Operation選択。
* PythonによるClarification生成または質問内容の決定。
* Conversation Quality Test専用、特定fixture専用、score改善専用の分岐。
* Python fallback回答の強化、固定回答、意味的なAction修復。
* `ConversationStateClassifier`、`TopicRouter`、`KeywordRouter`または同等責務の別名での追加。

LLM / AI Model Provider障害時に、Pythonが構造化errorを返す、安全に停止する、契約どおり機械的にretryすることは
許容する。取得済み文脈を解釈して「それらしい回答」を生成するfallbackは許容しない。

## Conversation Quality Testの位置づけ

Conversation Quality Testは自然な会話を観測する評価であり、回答文や内部実装を固定するものではない。同時に、
会話品質の改善を口実にPythonへ意味判断が戻ることを防ぐ **Python Brain Regression Guard** である。

評価対象には次を含める。

* 文脈維持と、明示された新しい話題への転換。
* 不要なToolを呼ばず、必要なときだけProvider Operationを呼ぶこと。
* 曖昧なときにLLMが必要なClarificationを返すこと。
* 回答が自然で読みやすく、ユーザーの依頼を満たすこと。
* Provider結果とObservationの制約を正しく使うこと。

ただし、これらの成否をPythonが意味判定して補正してはならない。決定的evaluatorはcall trace、Runtime gate、
Observation metadata、side effect等の構造化結果を検査できる。回答の自然さ、文脈理解、質問の適切さ等はsemantic
evaluatorまたは人間が評価する。テスト失敗は、context、prompt、Observation、Provider / Catalog契約、Memory、
model適合性の改善候補であり、直ちにPython分岐を追加する根拠ではない。

テストまたはレビューでは、禁止class名の有無だけでなく、同等責務のhelper、score、mapping、fixture特例も確認する。
Pythonの構造テストは「意味判断が存在しないこと」を補助できるが、命名検査だけを完全な証明とはしない。

## レビュー基準

会話、Context、Provider、Catalog、Memory、評価に関する変更では必ず次を確認する。

1. これはLLMに渡す材料の改善か、それともPythonによる判断の追加か。
2. Providerは候補、正本事実、構造化結果、Operationを返すだけで、意図や会話を判断していないか。
3. Catalogは宣言であり、keyword、`use_when`、score、固定優先順位を実行する判断表になっていないか。
4. Test、fixture、特定文言を通すためだけの分岐、mapping、fallbackがないか。
5. Pythonの処理は同じ構造化入力に対して説明可能で決定的であり、自然言語の意味に依存していないか。

一つでもPython意味判断に該当する場合、Conversation Quality改善としてmergeしない。必要ならLLM Contract、Runtime safety、
Providerの決定的ドメイン処理のどこに属するかを分けて再設計する。

## 影響

次に実装してよいのは、Context Assembly、prior turns / Observationのbudget管理、Observation metadata、Provider
Operation契約、Capability説明、Memory Provider、prompt、LLM Contract適合性、評価trace / rubricの改善である。

まだ実装してはならないのは、keyword / topic router、conversation classifier、過去Providerによる継続判定、
Python clarification、意味的fallback回答、テストケース専用分岐、Catalog ruleによる自動選択である。

## Jarvis Principle Check

1. Web UIから利用できるか: Web Chatも同じContext、LLM Contract、Runtime経路で品質改善を受ける。
2. API / Toolとして利用できるか: Chat APIとProvider OperationへChannel非依存で適用する原則である。
3. 将来MCP Tool化できるか: MCP metadataも判断表にせず、LLMが選ぶ宣言的契約として扱える。
4. Jarvis Coreから呼び出せるか: Coreが材料を組み立て、単一LLM Agent Loopへ渡す。
5. UI依存のロジックになっていないか: 意味判断をUIやChannelへ置かない。
6. 読み取り系か更新系か: 本Decisionはdocsのみ。将来の会話履歴・Memory更新には個別policyが必要である。
7. 副作用・権限・プライバシー上の注意: Context、Observation、Memoryは最小開示、visibility、retentionを守り、writeはRuntime gateを通す。
