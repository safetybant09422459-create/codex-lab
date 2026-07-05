# Domain Provider Contract v1

更新日: 2026-07-05

## 目的

Domain Provider Contract v1は、LLM Agent Loopが利用可能なOperationを発見し、選択済みOperationを
Runtime経由で安全に実行するためのtransport中立契約である。Providerは自然文を解釈せず、構造化された
Operationとargumentsだけを受け取る。

```text
LLM Agent Loop
  -> Operation Catalogを参照してprovider_id / operation_id / argumentsを選択
  -> Runtime: schema validation / permission / confirmation / audit
  -> Domain Provider
  -> Repository / Storage / External Adapter
```

## Contract v1

コード上の共通契約は`backend/domain_provider.py`に置く。

* `DomainProvider.provider_id`: Providerの安定ID
* `DomainProvider.operation_specs()`: Provider固有の能力説明、例、制約、実装状態
* `DomainProvider.execute()`: Runtime検査後のOperationを決定的に実行
* `OperationContext`: `operation_id`、`skill_id`、`mode`、`risk_level`
* result: Operation固有のstructured result。会話文ではない

ProviderはCRUD、検索、正本取得、外部API呼び出し、ドメイン不変条件、正規化を担う。ユーザー意図の解釈、
Operation選択、複数Providerの計画、Clarification、会話状態、最終回答はLLM Agent Loopが担う。

## Operation Catalog

`ProviderRegistry`は登録ProviderとTool JSONを結合し、`contract_version: "1"`のCatalogを返す。各Operationは
次を持つ。

* `provider_id` / `operation_id`
* `description`
* `what_it_can_do` / `what_it_cannot_do`
* `input_schema` / `output_schema`
* `mode`: `read` / `write` / `action`
* `risk_level`
* `confirmation_required`
* `audit_required`
* `examples`
* `limitations`
* `availability`: `implemented` / `planned`
* `tool_id`: Runtime Toolへ対応する場合のID

安全メタデータの正本は既存`tools/<skill>/*.json`である。CatalogはTool JSONのschema、mode、risk、
confirmationを投影し、Provider側の能力説明、非対応範囲、例、制約、実装状態を重ねる。これによりTool JSONと
Provider Catalogが異なるriskを宣言する二重管理を避ける。空のoutput schemaはv1 Catalog上では最低限の
`type: object`として公開するが、Operation固有schemaへの精密化は今後の契約改善対象である。

`planned` Operationは発見できるが、Runtimeは実行を拒否する。Catalog記載だけで実装済みとは扱わない。

Operation Catalogは宣言であり、発話からProvider / Operationを選ぶrouting tableではない。Capability Catalogは
人間向け能力説明、Dashboard Catalogは描画候補metadataとして別に扱う。Providerは3種類の候補を宣言できるが、
選択はLLM / Coreが行う。関係とguardrailは
[Catalog Principle / Guardrail](decisions/2026-07-catalog-principle.md)を参照する。

## Provider Registry

`backend/provider_registry.py`がProvider一覧、ProviderごとのOperation一覧、Operation解決を担う。v1では
`TravelProvider`を登録する。Registryは意味判断やrankingをせず、`provider_id + operation_id`の厳密一致だけを
扱う。

Catalog API:

* `GET /api/providers/operations`

## Runtimeとの関係

Core向け実行入口は`RuntimeService.execute_provider_operation()`、HTTP入口は
`POST /api/runtime/operations/execute`である。

```json
{
  "provider_id": "travel",
  "operation_id": "get_trip",
  "arguments": {"trip_id": "trip-1"},
  "confirmed": false,
  "role": "guest"
}
```

RuntimeはRegistryでimplemented Operationと対応Toolを解決し、既存の`execute_stub()`経路へ委譲する。
したがってTool JSONのinput schema検証、Permission Engine、Confirmation Engine、Audit Logger、
Executor Registryを迂回しない。既存`POST /api/runtime/execute`とTravel APIも互換のため維持する。

Travel writeは引き続き`admin`、`confirmed: true`、監査が必要である。CatalogやProviderを直接呼ぶことは
認可済みを意味しない。Core、将来MCP、REST、Webの実行入口はRuntimeを通す。

## Travel Operation

implemented:

* read: `get_trips`、`get_trip`、`get_trip_timeline`、`get_spot`、`get_experience`
* read / Photo連携: `get_trip_photos`、`get_spot_photos`、`get_experience_photos`、
  `get_experience_photo_search`、`get_experience_photo_links`
* guarded write: `create_trip`、`create_timeline_item`、`create_experience`、`update_experience`、
  `archive_experience`、`link_experience_photo`、`archive_experience_photo_link`、
  `set_trip_cover_image`、`set_spot_cover_image`

planned:

* `search_trip`
* `search_experience`

`get_spots`はTool JSONだけがあり、TravelProvider実装がないためCatalogへは公開しない。

## 将来MCPへの投影

MCP adapterはimplemented Catalog entryの`provider_id.operation_id`をTool名、`description`と能力説明をTool説明、
`input_schema`をMCP input schemaとして投影できる。MCP handlerは同じRuntime入口へ渡し、Providerを直接実行
しない。MCP transport、session、認証方式はv1範囲外であり、MCP接続自体を権限や確認の証拠にしない。
MCPはTool選択を担わず、MCP化後もLLM / CoreがOperationを選択する。

## Jarvis Status Provider

Jarvis Status Providerの`get_capabilities`、`get_provider_status`、`get_operation_catalog`は、CatalogやProvider状態の
許可されたread viewを構造化して返す。これはユーザー意図の解釈、Operation選択、Capability説明の最終回答生成を
Providerへ移すものではない。「何ができる？」という発話をPythonで`get_capabilities`へ固定routingせず、LLMが
Operation Catalogから必要性を判断し、Observationを基に回答する。

ユーザー目線のCapability Descriptionは各Providerに対応する`skills/<provider_id>/skill.json`の`capabilities`が
宣言する。Jarvis Status ProviderはCapability Catalogを決定的に集約するだけで、Provider別説明、優先順位、
ユーザー意図に基づく選択を持たない。metadataがないSkillには汎用的な未宣言表示を返す。Operation Catalogは
従来どおりOperation実行契約を返し、Capability Catalogとは分離する。この境界はCatalog Principleと
Conversation Quality / Python Brain Regression Guardに従う。

## 今回復旧しないもの

* `/api/chat`からのOperation選択・実行
* 単一LLM Agent Loop、tool-call反復、結果の十分性評価、Clarification、最終回答
* Travel Chat旧Router / Planner / Entity Resolver / Answer Generator互換
* `search_trip` / `search_experience`の検索・Entity確定
* MCP transport
* 実ユーザー認証と一般ユーザー向けConfirmation UI
* DB schema変更
