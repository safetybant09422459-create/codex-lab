# Decision: Jarvis Core Thinking Model

## 日付

2026-07-07

## Status

Accepted（責務モデル。Long-term Context retrievalは未実装）

## 背景

Jarvisには、Provider Principle、Capability Catalog、Conversation State、Observation Envelope、
Observation Guardrail、Observation Reference Principle、Entity Context、Long-term Context Principle、
Conversation Quality / Python Brain Regression Guardがある。これらを個別に適用するだけでは、CoreがLLMへ
何を渡し、LLMが何を判断し、RuntimeとProviderが何を実行するかという一つの推論経路が見えにくい。

本Decisionは既存原則を置き換えず、Jarvis Coreの一枚のThinking Modelとして統合する。ここでいう
Thinking ModelはLLMの内部思考やchain-of-thoughtを保存・公開するモデルではなく、LLMへ渡す判断材料と、
外部化されたAction、決定的実行境界の責務モデルである。

## 決定

Jarvis Coreは、認可、visibility、token budgetを適用した次の材料をContext Assemblyで組み立て、単一の
LLM Agent Loopへ渡す。

* User Input
* Conversation Context
* Observation
* Active Entities
* Long-term Context candidates
* Capability Catalog
* Operation Catalog
* Provider Responsibility

LLMはこれらを判断材料として、直接回答する、Provider Operationを呼ぶ、不足情報を質問する、取得済み
Observationを参照する、Long-term Context候補を推論へ利用する、のいずれが適切かを判断する。
Pythonはこの意味判断を行わない。

```text
User Input
    ↓
Context Assembly
    ├ Conversation Context
    ├ Observation
    ├ Active Entities
    ├ Long-term Context candidates
    ├ Capability Catalog
    ├ Operation Catalog
    └ Provider Responsibility
    ↓
LLM
    ↓
Direct Answer or Provider Operation
                    ↓
                 Runtime
                    ↓
                 Provider
                    ↓
                Observation
                    ↓
Conversation State / Context update
                    ↓
             same LLM Agent Loop
```

Provider Operationを選んだ場合、Runtimeがvalidation、permission、confirmation、audit、budget等を適用し、
許可されたOperationだけをProviderへ渡す。Provider ResultsはObservation Envelopeへ変換され、同じLLM
Agent Loopへ戻る。LLMが結果の十分性を評価し、回答、追加Operation、clarificationを判断する。

## 判断材料の責務

| 材料 | 責務 |
| --- | --- |
| User Input | 現在のユーザー入力。Channelによる決定的な正規化はできるが、intentやtopicを付与しない |
| Conversation Context | 直近の会話文脈。短期的な会話継続の材料であり、長期知識や正本ではない |
| Observation | この会話で得た取得時点の観測事実。現在値を保証するキャッシュではない |
| Active Entities | この会話で参照可能な、正本IDとprovenanceを持つ候補。参照先の確定や正本そのものではない |
| Long-term Context | 会話を越えて未来の推論を変える長期文脈。RecordやProviderのSource of Truthではない |
| Capability Catalog | Jarvisが利用可能な能力の宣言。routing、選択、回答を持たない |
| Operation Catalog | Runtime経由で実行可能または計画中の構造化Operation契約。実行許可や選択結果ではない |
| Provider Responsibility | 各Providerが担当する能力、Source of Truth境界、できること、できないこと |
| Provider Results | Repositoryまたは外部サービス等のSource of Truth由来の構造化結果。会話回答ではない |

Observationだけで回答に十分か、現在値をProviderから再取得すべきかはLLMが判断する。Active Entitiesは
参照候補をLLMへ渡すが、Pythonが「それ」とEntity IDを対応付けない。CatalogとProvider Responsibilityは
発見可能性と制約を提供するが、Provider / Operationを選択しない。

## LLMの責務

LLMは、与えられた材料とRuntime policyを基に次を判断する。

* Operationを使わず直接回答できるか
* どのProvider Operationを呼ぶか、そのargumentsは何か
* 安全に回答または実行するための情報が不足し、clarificationが必要か
* 取得済みObservationが今回の依頼に十分か
* Providerを再実行して現在値または追加Evidenceを取得すべきか
* 提示されたLong-term Context候補を今回の推論へ利用すべきか

LLMの内部chain-of-thoughtは契約、Conversation State、Observation、監査ログへ保存しない。Coreが扱うのは
入力材料と、`answer`、`ask_clarification`、`call_operation`等の検証可能なActionだけである。

## Python Brain禁止

Pythonがしてよいことは、意味を解釈しない決定的処理に限る。

* 保存
* 整形
* validation
* filtering
* visibility適用
* permission適用
* token budget適用
* deterministic context assembly
* Runtime execution

Pythonは次を行ってはならない。

* intent判定
* topic判定
* Provider選択
* Operation選択
* clarification生成
* answer生成
* Long-term Contextの意味的な利用判断
* Observationを使うかProviderから再取得するかの判断

schema validation、principal / permission / visibilityによるfilter、件数・byte・token上限による決定的な
切り詰め、Provider IDとOperation IDの厳密解決は許可される。発話の意味、重要度、関連度、話題をPythonで
推測して同じ処理を行うことは禁止する。

## Long-term Context retrieval

Long-term Contextは全件をLLMへ渡さない。visibility、permission、token budget内の候補だけをretrievalで
Context Assemblyへ渡し、その候補を実際に利用するかはLLMが判断する。

今回はretrievalを実装せず、retrieval方式、保存DB、embedding、RAG実装を決定しない。Memory Providerの
設計も行わない。将来方式を選定しても、候補取得と候補の意味利用を分離し、Long-term ContextをDomain
ProviderのSource of TruthやObservationへ変えない。

## Provider化の判断基準

Providerはデータを保存するためではなく、Jarvis Coreへ新しい能力を提供するために存在する。ある情報を
Providerへ構造化する基準は件数、保存量、永続化の都合ではなく、次の問いである。

> 構造化することで新しい検索・操作・能力が生まれるか。

答えが「はい」の場合にProvider化を検討する。単に情報が増えた、DBへ保存したい、長期間保持したいという
理由だけではProvider化しない。Providerは決定的なCRUD、検索、操作、正本取得、外部API連携、ドメイン不変条件を
担い、意図解釈、会話、結果の意味評価、最終回答を担わない。

## 既存原則との関係

* Provider Principle / Domain Provider Boundary: Providerは能力提供とSource of Truth取得を担い、頭脳にならない。
* Capability Catalog / Operation Catalog: LLMへ能力と実行契約を宣言するが、選択ロジックを持たない。
* Conversation State / Conversation Context: 短期の会話継続材料を保存し、決定的に組み立てる。
* Observation Envelope / Guardrail: Provider Resultsをprovenanceと利用条件付きの観測事実として戻す。
* Observation Reference Principle: Observation参照かProvider再取得かをLLMが判断する。
* Entity Context: Active Entitiesを候補として渡し、Pythonで参照解決しない。
* Long-term Context Principle: token budget内の候補だけを渡し、意味利用はLLMが判断する。
* Python Brain Regression Guard: 会話品質を入力材料と契約の改善で上げ、Pythonへ意味判断を戻さない。

## 非対象

* API、Tool、Runtime、Provider、frontend等のコード変更
* DB設計またはmigration
* Long-term Context retrieval方式の決定または実装
* embeddingまたはRAGの実装
* Memory Providerの設計
* 新しいProvider OperationまたはCapabilityの追加

## 再検討条件

この材料区分では代表的な会話を表現できない、または単一LLM Agent LoopとRuntime境界では安全性、品質、
latency、costを満たせないことが評価で確認された場合に再検討する。その場合も、Pythonへ意味判断を移す前に、
材料の契約、説明、provenance、budget、LLM Contractを見直す。

## Jarvis Principle Check

1. Web UIから利用できるか: Web ChatをChannelとして同じThinking Modelへ接続できる。
2. API / Toolとして利用できるか: API / ToolはRuntimeとProvider Operation境界から同じモデルを利用できる。
3. 将来MCP Tool化できるか: Operation CatalogをMCPへ投影しても、判断はJarvis Core / LLMに残せる。
4. Jarvis Coreから呼び出せるか: 本DecisionはCoreのContext Assemblyと単一LLM Agent Loopの責務モデルである。
5. UI依存のロジックになっていないか: Channel非依存であり、UIは入力と表示のadapterに限る。
6. 読み取り系か更新系か: 今回はdocs変更のみ。モデルはreadとguarded write / actionの両方を扱う。
7. 副作用・権限・プライバシー上の注意: 最小開示、visibility、permission、token budgetをAssembly前に適用し、write / actionはRuntimeの確認と監査を通す。
