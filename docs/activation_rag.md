# Jarvis Core Activation RAG

## Status

本書はJarvis CoreにおけるActivation RAGの設計基準を定める。目的はTravel RAGを作ることではない。
Travelは共通契約を検証する最初のProvider / PoCであり、CoreへTravel固有の型、語彙、検索規則を
持ち込まない。

現在のPoCは、共通Document、in-memory lexical index、Travel Provider、Chat Routerへのread-only
候補注入までを検証している。Photo、Calendar、Memory Provider、永続index、Knowledge Enrichment連携、
Capability Usage RAGは未実装である。

## Activation RAGとは

Activation RAGは、現在の発話から「どの正本Entityや能力を詳しく調べるべきか」を軽く広く想起する
Jarvis Coreのread-only検索層である。

* **DBの代替ではない。** DBの内容を回答用の正本として複製するものではない。
* **DBを思い出すための索引である。** 曖昧な言葉から正本Entityの参照候補を返す。
* **Runtimeの代替ではない。** Tool validation、Permission、Confirmation、Audit、実行を担当しない。
* **Entity Resolutionを補助する。** 候補集合と検索理由を渡すが、Entityを最終確定しない。

検索結果はEvidenceでも実行許可でもない。score 1位、単一候補、LLMによる選択のいずれも正本確認や
Runtime Gateを省略する根拠にならない。検索障害時は候補なしでChatを継続し、別SkillやActionを
推測実行しない。

```text
User message + authorized context
  -> ActivationSearch
       -> Provider
            -> Repository (canonical read)
            -> Builder
            -> RagDocument projection
       -> Search index
  -> RagSearchResult candidates (unverified)
  -> Chat Core / Entity Resolver
  -> Runtime Gate (when a Tool is needed)
  -> Repository canonical read
  -> Evidence Assembly
  -> Answer
```

## Source of Truth

真実として扱うのは、各Domainの**SQLiteデータ**と、それを読む**Repository**だけである。

| Component | 扱い |
| --- | --- |
| SQLite | Domain Entityを永続化する正本 |
| Repository | 正本を読み書きするDomain境界。返却値はその時点の正本snapshot |
| RagDocument / search index | 正本から再生成できる検索Document。非正本 |
| RagSearchResult | query時点の候補とranking。非正本 |
| Enrichment candidate | 未承認の派生候補。非正本 |

Activation RAGへ保存されたtext、metadata、alias、tag、embeddingは真実ではない。回答前に
`entity_id`をProviderがRepository参照へ解決して再取得する。正本の更新・削除・visibility変更時はDocumentを
invalidateまたは再生成できなければならない。RAG indexだけから正本を復元する設計は禁止する。

## Core contracts and responsibilities

Core契約はProvider中立にする。`trip_id`、`place_id`、`prefecture`、`travel_day`等のTravel固有fieldや、
Travel固有の`entity_type`列挙をCore型へ追加しない。

### RagDocument

正本Entityを検索可能にした再生成可能なprojectionである。

| field | meaning |
| --- | --- |
| `id` | Provider内で安定し、全Providerで一意になるDocument ID |
| `source_skill` | Documentを生成したProvider owner ID。PoCの既存field名 |
| `entity_id` | Repositoryで正本を再取得するopaqueな参照 |
| `entity_type` | Providerが定義する文字列。Coreは値を列挙しない |
| `text` | recall用の最小検索text。回答用の正本ではない |
| `metadata` | filter / ranking用の非正本projection。schemaはProvider所有 |
| `visibility` | 正本から継承した閲覧境界 |
| `updated_at` | projection元の鮮度判定用時刻 |

将来の永続index化では`schema_version`を追加する。`source_skill`は既存API互換の名称であり、Coreは
Skill固有処理に使わずProvider ownerの識別子としてだけ扱う。

Coreが依存してよいのは共通envelopeだけである。Provider固有metadataをCoreが解釈してroutingや
回答を行わない。検索結果を外部LLMへ渡す場合もtext全量ではなく必要最小限のhintへ縮小する。

### RagSearchResult

`RagDocument`への参照、正規化score、matched terms、ranking reasonを持つ検索候補である。
認可scopeとindex versionを診断可能にする一方、秘密本文をdebug / Auditへ複製しない。

`RagSearchResult`は次を保証しない。

* Entityが現在も存在すること
* ユーザーの質問に対する答えであること
* Toolを実行してよいこと
* metadataが最新または完全であること

### ActivationSearch

Provider横断検索を調停するCore serviceである。

* query、認証主体、purpose、visibility、limit、Provider filterを受け取る
* 認可されたProvider / Documentだけを検索する
* rankingし、上限件数の`RagSearchResult`を返す
* timeout、部分障害、空結果をChatから分離する
* Entityの確定、正本取得、Tool実行、回答生成は行わない

検索backendはこの境界の内側で交換可能にする。PoCのin-memory lexical searchからSQLite FTS5、
lexical + vector hybrid、外部vector storeへ移行しても、Core / Provider契約は変えない。

### Provider

DomainとActivation RAGのadapterである。

* 認可済みRepository readを使って正本snapshotを取得する
* BuilderへDomainデータを渡し、Documentを列挙または差分提供する
* visibility、削除、更新versionを正本から継承する
* Domain固有のalias、語彙、projection方針を所有する
* 正本を更新せず、Runtimeを迂回せず、他Providerのmetadataを解釈しない

Providerは検索engineでもRepositoryでもない。CoreはProvider登録と共通ライフサイクルだけを扱う。

### Builder

Domain Entityから`RagDocument`を作る純粋なprojection責務を持つ。

* 安定したDocument / Entity参照を作る
* recallに必要な最小textとmetadataを選ぶ
* visibility、source timestamp、schema versionを付ける
* 承認済みEnrichmentだけを検索projectionへ反映する
* DB更新、検索、LLM呼び出し、Permission判断を行わない

### Search index / store

Documentのupsert、delete、filter、rankingを担当する派生Storeである。Source of Truthではなく、常に
破棄・再構築可能にする。外部indexを使う場合もtenant / owner / visibility filterを検索後ではなく
検索前または検索と同時に適用する。

## Provider policy

| Provider | Status | Search target | Boundary |
| --- | --- | --- | --- |
| Travel Provider | PoC | Trip / Experience等の正本参照候補 | Travel RepositoryとTravel Builderが固有schemaを所有する |
| Photo Provider | Future | Photo Asset / Album等の正本参照候補 | EXIF、人物、撮影場所、Photo権限をPhoto側で扱う |
| Calendar Provider | Future | Event等の正本参照候補 | busy / private等のvisibilityをCalendar側で扱う |
| Memory Provider | Future | 承認済みMemoryの参照候補 | 会話ログそのものとMemoryを混同しない |
| Home Provider | **対象外** | なし | Homeは現実世界へ作用するAction。Action schemaとRuntime Gateを使う |

「テレビつけて」「電気を消して」のようなHome要求をRAG検索結果から実行してはならない。Homeの
状態取得も、Action / Tool契約と権限設計を先に定義し、Activation RAG Provider追加の口実にしない。

## Knowledge Enrichmentとの関係

Knowledge Enrichmentは検索を育てる候補生成であり、Activation RAGは承認済みprojectionを検索する。

```text
conversation
failed / zero-result / ambiguous search
user correction or explicit selection
  -> Learning Event (minimum necessary data)
  -> alias candidate
  -> tag candidate
  -> search-document update candidate
  -> review / approval / rejection
  -> approved projection
  -> Builder rebuilds RagDocument
```

EnrichmentからTravel、Photo、Calendar、Memory等の本体DBを更新することは禁止する。ユーザー修正は
強いsignalだが、それ自体はDomain factではない。候補はsource、source_ref、confidence、status、
visibility、lifecycleを持つ別Storeで管理し、承認済み候補だけをBuilderが利用する。

本体DBの修正が必要なら、Activation / Enrichmentとは別の明示的Domain writeとして、Permission、
Confirmation、Auditを通す。

## Capability Usage RAG

Capability Usage RAGは、**SkillそのものではなくSkill / Toolの使い方**を検索対象にする将来案である。
Capability Catalogを置き換えず、Catalogが大きくなったときに現在発話に近い利用例や選択条件を
想起する補助indexとする。

| User utterance | Retrieved usage candidate | Next boundary |
| --- | --- | --- |
| 「テレビつけて」 | Home Actionを使う | Home Tool schemaを選び、Runtime Gateへ。Memory Searchはしない |
| 「神戸で何した？」 | Travelの記録検索を使う | Travel Provider候補をEntity Resolutionし、Repository readへ |
| 「写真ある？」 | Photo検索を使う | Photo Provider / Photo read Toolへ |

Action ToolとMemory Searchは別物である。

* **Action Tool**は現実世界やデータへ作用する。schema、risk、Permission、Confirmation、Auditが必要。
* **Memory / Domain Search**は既存の正本を探すreadである。visibility、purpose、再取得が必要。
* Capability Usage候補はどちらを使うべきかの発見を補助するだけで、Tool callや権限を生成しない。

usage Documentにはsource、version、approval status、confidence、適用範囲、有効期間が必要になる。
失敗したTool選択や一時的なLLM出力を自動学習しない。実データDocumentとはcorpus、ranking signal、
評価指標を分ける。今回は設計評価だけとし、実装しない。

評価上の利点はCapability増加時のprompt削減と自然な言い換え対応である。主なリスクは、古いusageが
誤ったToolへ誘導すること、Actionとreadを混同すること、検索上位を実行許可と誤認することである。
したがってCatalog fallback、version失効、承認workflow、Action / Search分類のhard boundaryが
導入条件になる。

## Travel PoCの位置付け

Travel Providerは、SQLite-backed Travel RepositoryからTrip / Experience相当の正本を読み、Travel
Builderで共通`RagDocument`へ投影する最初のcontract testである。地域、日付、place、timeline等の
Travel語彙とmetadataはTravel側だけに置く。

PoCで検証するもの:

* Provider / Builder / Searchの分離
* 曖昧な発話から複数Entity候補を返せること
* visibility filterと正本再取得の経路
* 検索失敗時にBasic Chatを壊さないこと

PoCで証明しないもの:

* Activation RAG全体がTravel向けであること
* lexical scoreがEntity確定に十分であること
* indexが正本として利用できること
* Travel aliasをCoreへ昇格してよいこと

## Implementation roadmap

1. 共通契約からTravel固有型を除き、Provider / Builder contract testを固定する。
2. 認証主体、owner、visibility、purposeを含む`ActivationSearch` requestを定義する。
3. Travel PoCでzero-result、曖昧性、削除、visibility変更、stale Documentを評価する。
4. Provider registryとincremental upsert / delete / rebuild lifecycleを追加する。
5. SQLite FTS5と現行lexical rankingを日本語benchmarkで比較する。
6. Photo、Calendar、Memoryの順にProviderを追加し、Provider間の権限漏えいを評価する。
7. Enrichment candidateのreview / approval後にだけDocument再構築へ接続する。
8. Capability Usage RAGを別corpusの実験として評価し、Action / Search誤分類率を導入判定に使う。

## Safety and privacy

Activation検索はread-onlyだが、検索対象は旅行、位置、写真、予定、家族、会話由来情報を含み得る。
検索前の認可、purpose binding、外部AIへの最小送信、削除 / Forget連動、debug / Auditの本文抑制が
必要である。検索Documentの生成やembedding作成も、元データより広いvisibilityを持ってはならない。

## Jarvis Principle Check

1. **Web UIから利用できるか**: Chat API経由で利用可能。UI固有実装は不要。
2. **API / Toolとして利用できるか**: Core serviceとして呼べる。公開Tool化時も検索結果は候補に限定する。
3. **将来MCP Tool化できるか**: 共通request / result契約を保てば可能。認証・visibility・purposeを必須にする。
4. **Jarvis Coreから呼び出せるか**: Context Assembly / Entity Resolution前のread-only補助として呼び出す。
5. **UI依存のロジックになっていないか**: Provider、Builder、SearchはいずれもUI非依存である。
6. **読み取り系か更新系か**: 検索はread。index再構築は派生projection更新であり、Domain更新ではない。
7. **副作用・権限・プライバシー上の注意**: Domain副作用は禁止。検索前認可、最小化、失効、監査が必要。
