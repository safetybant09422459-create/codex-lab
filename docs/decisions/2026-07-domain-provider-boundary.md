# Decision: Domain Provider Responsibility Boundary

## 日付

2026-07-05

## Status

Accepted

## 背景

JarvisはWeb、Chat、Voice、Camera、Notification、将来のAgentから、同じ生活能力を再利用する生活OSを目指す。
従来のSkillはユーザー向け能力領域と実装境界の両方を指し、Core、Runtime、Repository、外部サービスとの
責務が曖昧になり得た。一方、Jarvis vNextは意味判断をLLM Agent Loopへ集約し、Pythonに第二の頭脳を作らない。

また、既存文書の `Provider` にはAIモデル提供元とActivation RAGの文書供給実装という別の意味があるため、
Domain Providerとの区別が必要である。

## 決定

* Skillはユーザーから見える能力・機能単位として名称を維持する。
* Domain Providerは、そのSkillがJarvis Coreへドメイン能力を提供する契約境界とする。
* Providerは実装方式ではない。MCP、REST API、Local Serviceのいずれでも同じ責務とOperation契約を果たす。
* MCPを現時点の第一候補とするが、CoreとProvider ContractはMCPへ依存しない。
* ProviderはSkillと並ぶ新しい頭脳、必須microservice、または第七のトップレベル責務にはしない。

```text
Channel
  -> Jarvis Core boundary
       -> LLM Agent Loop: 意味理解、Provider / Operation選択、組み合わせ、質問、回答
       -> Runtime: Validation、Permission、Confirmation、Audit、安全な実行
            -> Domain Provider Contract
                 -> Repository / Storage / External Adapter
```

Providerが担当する:

* CRUD、検索、正本データ取得、Repository / DBアクセス
* 外部API呼び出し、Operation実行
* ドメイン不変条件、正規化などの決定的なドメインロジック
* Provider内部の低レベルdispatch、Repository選択、外部API fallback

Providerが担当しない:

* ユーザー意図の解釈
* Provider / Operationの会話上の選択
* 複数Providerの組み合わせと結果の意味評価
* Clarification、Persona、会話状態、最終回答
* Runtimeの安全機能の迂回または代替

Provider Operationは構造化入力、構造化結果またはエラー、read/write、risk、sourceを明確にする。writeは
入口やtransportにかかわらずRuntimeを通し、Permission、Confirmation、Auditを適用する。

## Skillとの関係

通常は1つのSkillが同名ドメインのProvider契約を所有する。例えばTravel SkillはTravel Provider Contractを
通じて `search_trip`、`get_trip`、`update_trip`、`search_experience` 等のOperationを提供し、その内部で
Travel Repository、Travel DB、外部API Adapterを利用できる。

Skillは画面、利用者向け説明、Capability Catalog上のまとまりを含み得る。ProviderはCoreから利用する
Operation境界に限定する。したがってSkillとProviderは1対1を強制せず、将来の分割・統合でもCore側の契約を
維持できるようにする。

Provider間連携をProvider内部へ隠して会話上の計画を固定しない。複数Providerを使う必要性と順序はLLM Agent
Loopが判断し、各OperationはRuntimeを通る。Provider内部では、1つのOperationを完了するための決定的な
下位処理だけを組み合わせてよい。

## 用語

* `Domain Provider`: Coreへドメイン能力を提供する本Decisionの境界
* `AI Model Provider`: OpenAI、Claude、Gemini、Local AI等のモデル提供元
* `Activation RAG Provider`: 正本から検索Document候補を供給するActivation RAG内部実装
* `External Service Provider`: Google Places、Immich等。Domain Provider内部のAdapter先

文脈が曖昧な文書では、単独の `Provider` ではなく上記の修飾名を使う。

## 影響

* Web UIとJarvis Chatは画面専用・Chat専用ドメイン処理を増やさず、同じProvider Operationを利用する。
* CoreはProviderのtransport、Repository、DB、外部APIを知らずに能力を組み合わせられる。
* 既存Executor / Repository構造はLocal Provider実装として段階的に扱え、一括renameやコード変更は不要である。
* Provider Contractの具体schema、discovery、versioning、transport adapterは実装時に別途決定する。

## Jarvis Principle Check

1. Web UIから利用できるか: 同じProvider OperationをRuntime経由で利用できる。
2. API / Toolとして利用できるか: Provider ContractがOperation / Tool境界を定義する。
3. 将来MCP Tool化できるか: MCPを第一候補としつつ、契約はtransport中立に保つ。
4. Jarvis Coreから呼び出せるか: Coreが利用する能力提供境界そのものである。
5. UI依存のロジックになっていないか: ProviderはUI状態や表示判断を持たない。
6. 読み取り系か更新系か: 両方を扱い、各Operationでread/writeとriskを宣言する。
7. 副作用・権限・プライバシー上の注意はあるか: write、写真、予定、位置、在宅、家族情報、外部送信はRuntimeの権限、確認、監査、データ最小化を必須とする。
