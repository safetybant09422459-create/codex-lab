# Decision: Catalog Principle / Guardrail

## 日付

2026-07-05

## Status

Accepted

## 背景

Jarvisは、LLM Agent LoopがOperation Catalogを参照し、Runtimeを経由してDomain Providerを実行する経路を
持ち始めた。今後CapabilityやDashboard候補を増やすとき、Catalogをユーザー発話に対する判断表、routing rule、
固定優先順位の置き場にすると、Pythonが第二の頭脳になり、ChannelやProviderごとに意味判断が分散する。

## 決定

**Catalog is declarative, not decision logic.**

Catalogは「何が存在し、どの契約・制約・表示能力を持つか」を宣言する。ユーザーの意図から「何を選ぶか」、
複数候補を「どう組み合わせるか」、現在「何を見せるか」は決めない。description、example、limitationはLLMが
判断するための資料であり、Pythonが発話と照合する条件式ではない。

### Catalogの分離

| Catalog | 目的 | 主な宣言 | 判断しないこと |
| --- | --- | --- | --- |
| Operation Catalog | LLMがDomain Provider Operationを発見・選択するための内部契約 | `provider_id`、`operation_id`、description、input / output schema、risk、examples、limitations、availability | 発話に基づくProvider / Operation選択、arguments推測、会話 |
| Capability Catalog | Jarvisが提供できる能力を人間に自然に説明するための一覧 | capability ID、「旅行を確認できる」「写真を探せる」等の説明、visibility、関連参照 | Operationの直接列挙、発話routing、最終回答の固定文 |
| Dashboard Catalog | UIが描画できるカード・ウィジェット候補の一覧 | candidate ID、表示種別、必要データ、対応renderer、visibility等のmetadata | 今表示する候補、並び順、提案優先度、ユーザー意図 |

3つは目的と利用者が異なるため、一つの万能Catalogへ統合しない。相互参照は安定IDで行えるが、参照関係を
選択ルールとして実行しない。Catalog entryの存在は、実装済み、実行許可済み、回答根拠、表示決定を意味しない。

### 正本と派生view

各Catalogは目的ごとに正本を一つだけ持つ。Operationのschema、mode、risk、confirmation、audit等の安全metadataは
Provider ContractとRuntime Tool定義の既存正本から決定的に投影し、CapabilityやDashboard側へ値を複製しない。
Capability CatalogとDashboard CatalogはOperation Catalogの別名や実行tableではなく、それぞれ人間向け能力説明と
描画候補を表すread modelである。

LLM向けcontext、Jarvis Status Providerの応答、API response、MCP Tool metadata、UI向け候補は、正本Catalogから
principal / permission / visibility、schema version、transport上の制約を適用して作る派生viewとする。派生viewへ
routing rule、固定回答、表示優先順位を追加せず、派生viewを認可、実装状態、Evidenceの新しい正本にしない。

### 責務

* **LLM / Jarvis Core**: ユーザー意図の解釈、Provider / Operation選択、複数Providerの組み合わせ、Capability
  説明の最終回答生成、Dashboardに今出す候補の選択を担う。
* **Python / Runtime**: Catalog読込、schema validation、principal / permission / visibilityによる決定的filter、
  versioning、transport mapping、安全検査、Provider実行、選択済み候補データのUIへの受け渡しを担う。
* **Domain Provider**: 自分のOperation、Capability、Dashboard候補を宣言し、実データ取得・更新と決定的な
  ドメイン処理を担う。ユーザー意図や会話上の選択を判断しない。
* **UI**: Coreから受け取ったカードや候補を描画する。発話やユーザー意図から候補を選択しない。

principal / permission / visibility filterは、候補を安全に除外する決定的なpolicyであり、意味上のrankingではない。
filter後の候補から何を使うかはLLM / Coreが判断する。schema validation、version compatibility、厳密ID解決も
同様に許可する。

## 禁止する設計

* ユーザー発話のkeyword、正規表現、score、固定ruleによるProvider / Operation選択
* 「旅行」を含めばTravel、「何ができる？」なら`jarvis.get_capabilities`という対応表
* Channel別またはProvider別の会話判断、Python fallback回答
* exampleや`use_when`をPythonのrouting条件として評価すること
* 提案カードの固定優先順位、Dashboard表示条件をCatalogやUIのif分岐へ蓄積すること
* Capability CatalogをOperation Catalogの別名または全Operationの利用者向け露出にすること
* Catalog entryを認可、Confirmation、Evidence、実装状態の代替にすること

## 許可する設計

* ProviderによるOperationと関連Capability / Dashboard候補の宣言
* description、input / output schema、risk、examples、limitations、availabilityの宣言
* Capabilityの人間向け説明とDashboard候補の描画metadata
* principal / permission / visibilityによる決定的filter、schema validation、versioning
* transport mappingとOperation CatalogからMCP Tool metadataへの投影

## Domain Provider Contractとの関係

Operation Catalogは[Domain Provider Contract](../provider_contract.md)の一部であり、ProviderがCoreへ公開する
実行契約である。Capability CatalogとDashboard CatalogはProviderが候補を宣言できる別のread modelであり、
`execute()`のdispatch表でもRuntime認可の正本でもない。安全metadataの正本、実装状態、Runtime gateは既存契約に
従い、Catalog間で矛盾する値を二重管理しない。

Jarvis Status ProviderはCatalog判断を代行するProviderではない。`jarvis.get_capabilities`、
`jarvis.get_provider_status`、`jarvis.get_operation_catalog`は、許可されたprincipalに対して現在の宣言や状態を
構造化して返すread-only Operationである。これらを呼ぶか、結果をどう説明するかはLLM / Coreが判断する。
「何ができる？」をPythonで`jarvis.get_capabilities`へ固定routingしてはならず、Providerは固定回答を返さない。

## MCPとの関係

MCPのTool name、description、input schemaは、implementedなOperation Catalog entryから投影できる。
Jarvis Operation Catalogはtransport中立な内部契約であり、MCPはその公開・呼出しに使えるprotocol / transportである。
MCP adapterはmapping、schema変換、version処理を担えるが、ユーザー意図、Tool選択、回答を判断しない。
MCP化後もToolを選ぶのはLLM / Coreであり、実行は同じRuntimeのPermission、Confirmation、Auditを通る。

## 影響

次に実装してよいのは、3 Catalogのschemaとversion、Provider宣言の集約、決定的filter、validation、MCP投影、
選択済みDashboard候補を描画するUIである。実装前にCatalogごとの正本と重複metadataの解消方法を決める。

まだ実装してはならないのは、発話keyword router、Catalog rankingによる自動選択、Channel / Provider別planner、
Python回答fallback、固定カード優先順位、UI内のDashboard選択ロジックである。

## レビュー時のGuardrail

Catalogまたはそのconsumerを変更するときは、少なくとも次を確認する。

* 追加fieldは「何が存在し、どの契約・制約を持つか」の宣言か。それとも「この発話なら何を選ぶか」という判断か。
* description、example、tag、score、`use_when`等をPythonが発話と照合していないか。
* principal / permission / visibility filterが安全な除外に限定され、残った候補の意味的rankingをしていないか。
* Operation、Capability、Dashboard間で安全metadataや実装状態を二重管理していないか。
* Jarvis Status Provider、MCP adapter、UIがCatalogを決定的に投影・描画するだけで、選択や回答を代行していないか。
* Catalog entryの存在だけでRuntime gate、Repository再取得、Confirmation、Auditを省略していないか。

一つでも意味判断または安全境界の代替に該当する場合、その処理はCatalogへ追加しない。必要な判断材料は宣言として
改善できるが、その材料から何を選ぶかはLLM / Jarvis Core、実行可否はRuntimeに残す。

## Jarvis Principle Check

1. Web UIから利用できるか: Capability説明と選択済みDashboard候補を共通契約から表示できる。
2. API / Toolとして利用できるか: Operation CatalogはProvider Operationの内部契約として利用できる。
3. 将来MCP Tool化できるか: implemented OperationをMCP metadataへ決定的に投影できる。
4. Jarvis Coreから呼び出せるか: Coreがfilter済みCatalogをLLMへ渡し、選択を担う。
5. UI依存のロジックになっていないか: Dashboard Catalogは描画候補だけを宣言し、表示判断をUIへ置かない。
6. 読み取り系か更新系か: Catalog読込はread。Operationのread / writeは各契約で宣言しRuntimeが検査する。
7. 副作用・権限・プライバシー上の注意: filterはprincipal / permission / visibilityを強制し、Catalog自体を認可や実行許可にしない。
