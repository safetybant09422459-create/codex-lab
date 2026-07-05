# Domain Provider Contract

更新日: 2026-07-05

## 目的

Domain Providerは、Jarvis Core / Runtimeから見える能力実行境界である。Providerは、Core / LLMが
選択済みのOperationとschema適合済みargumentsを受け取り、Repositoryまたは外部Adapterを通じて
structured resultを返す。

```text
LLM Agent Loop
  -> selected Operation + arguments
  -> Runtime: schema / permission / confirmation / audit
  -> Domain Provider
  -> Repository / Storage / External Adapter
```

## 最小契約

現行コードでは`backend/domain_provider.py`の`DomainProvider`と`OperationContext`を共通境界とする。

* `operation_id`: Tool JSONの`id`。別のCapability metadataを作らない。
* `skill_id`: Tool JSONの所有Skill。
* `mode`: `read` / `write` / `mixed`。
* `risk_level`: Runtimeが検査したrisk metadata。
* `arguments`: Tool input schemaに対してRuntimeが検証した構造化入力。
* result: Operation固有のstructured result。会話文ではない。

Tool JSONをOperation catalogの正本として維持する。ProviderはTool schema、Permission、Confirmation、
Auditを再定義せず、Runtimeを迂回して公開しない。

## Providerが行うこと

* 選択済みOperationのdeterministic dispatch
* canonical IDと型の検証
* Repository / Storage / External Adapterの選択
* CRUD、検索、正規化、ドメイン不変条件
* source、canonical ID、limitationsを含むstructured resultの返却

## Providerが行わないこと

* 自然文の解析、意図推定、Provider / Operation選択
* Entity候補の会話上の自動確定
* Clarification、会話状態、人格、最終回答
* Permission / Confirmation / Auditの迂回
* Activation RAG候補を正本やEvidenceとして扱うこと

## Travelの現在地

`TravelProvider`は既存Travel Tool IDをOperation IDとして受け取り、`TravelRepository`へdispatchする。
`TravelExecutor`はRuntime Tool metadataを`OperationContext`へ変換する薄いadapterになった。Travel DBと
Repositoryは正本のままで、read/writeは引き続きRuntime gateを通る。

`search_trip`、`search_experience`、`update_trip`はまだ正式契約ではない。次段階で、既存の
`get_trips`等との重複、検索結果のcandidate/verified状態、visibility filter、pagination、更新時の
optimistic concurrencyとidempotencyを決めてからTool JSONとして追加する。

## Transport

Provider契約はlocal Python call、REST、MCPのいずれにも載せられる。次段階ではまず同一Operation catalogを
MCP Toolへ投影できるadapterを設計し、Runtime gateをMCP serverの内側または必須gatewayとして保持する。
MCP transport自体に認可済みという意味を持たせない。
