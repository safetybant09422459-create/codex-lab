# Jarvis Context Assembly

> Router前の軽量な候補想起は[Jarvis Core Activation RAG](activation_rag.md)を参照する。PoCでは
> visibility filter済み候補を未検証hintとして渡し、正本EvidenceはRuntime後に組み立てる。

## Purpose

Context AssemblyはJarvis Chat Coreの中心であり、Plannerの前処理ではない。目的は、LLMが通常回答、
Capability利用、Tool利用、clarificationを適切に選べるよう、必要な情報を順序、出所、信頼度、
権限、token budget付きで一つのTurn入力へ組み立てることである。

LLMが頭脳として意味判断を行い、Pythonは安全で再現可能な入力と実行基盤を提供する。Pythonは
自然言語キーワードでSkillを先に決めない。

## Conversation Context Builder（最小実装）

現行の`backend/conversation_context.py`は、Conversation StateをLLM Contractへ渡すcontextへ機械的に
投影する。Agent HostはBuilderへ保存済みturn、Capability Description、session metadata、principalに対して
許可済みのvisibility集合を渡す。Builderは次を決定的に整形するだけである。

* `context_version`、`session_id`、channel、会話開始時刻
* 設定件数内の直近turn（古い順から新しい順）
* 最新turnのLLM Action、Observation、`active_entities`
* Provider Registryが宣言した全Capability Description
* 件数上限とcontext assembly部分のUTF-8 byte上限
* 明示的な機密keyの再帰的redaction
* 明示的な`visibility`値と許可集合の一致によるfilter

byte上限を超える場合は、会話履歴、Observation、active entity、Capabilityの順に各リストの古い要素を
除外し、最後に直近LLM Actionを除外する。要約、言い換え、重要度評価は行わない。固定metadataだけで上限を
超える場合は失敗させ、内容を推測して縮めない。

Builderは禁止事項として、topic / keyword判定、会話継続判定、Provider / Operation選択、arguments推測、
Clarification生成、意味要約を持たない。「旅行だから」「昨日だから」等の自然言語値はopaque dataとして扱う。
Capabilityは発話に応じてPythonが絞らず、visibilityと機械的上限を適用した宣言順でLLMへ渡す。判断は単一の
LLM Agent Loopが行う。

## Assembly order

入力は原則として次の順序で構成する。

1. **System Prompt**: Jarvisの役割、禁止事項、出力契約、Evidence規則
2. **Personality / Behavior**: 話し方、Basic Chatを優先する規範
3. **User Profile**: 認可済み主体、言語、timezoneなど必要最小限
4. **Working Context**: 直近3〜5Turn。短期会話でありMemoryではない
5. **Activation RAG candidates**: 認可scope内で薄く検索した上位候補。未検証hint
6. **Capability Catalog**: Jarvisが利用できる全Capabilityの概要
7. **Current World**: server-side現在日時、timezone、必要時の位置・天気・家の状態
8. **User Message**: 現在発話。履歴やMemoryより優先する

各sectionには出所と信頼区分を付け、ユーザー入力、client hint、検索候補、Runtime Evidence、
server-owned事実を混同しない。秘密情報はAssembly前に除去し、LLM Providerへは目的に必要な最小限
だけを渡す。

## LLM turn contract

第一Turnの共通結果は概念上、次のいずれかとする。

* `direct_answer`: 通常知識、Current World、既に与えた安全なcontextだけで回答できる
* `need_capability_detail`: Capabilityは必要だがTool詳細がまだない
* `tool_call`: 提示済みToolの検証可能な呼び出し提案
* `clarification`: 回答または安全な実行に必要な情報が不足する

挨拶や自己説明にPlanやToolを要求しない。現在時刻はCurrent Worldから答えられ、ユーザー固有
データが不要ならSkillを使わない。`need_capability_detail`は実行許可ではなく、Pythonが選択済み
CapabilityのTool schema、risk、Evidence契約を次Turnへ追加する要求である。

## Capability Catalog

CapabilityはLLM向けの能力説明であり、Skill / Tool / Executorという内部単位とは分離する。
最小項目は次を想定する。

| field | purpose |
| --- | --- |
| `capability_id` | 安定した能力ID |
| `summary` | 何を実現できるか |
| `use_when` | どのような必要に使うか |
| `evidence_types` | 取得できる根拠の種類 |
| `access_class` | public / personal / family / sensitive等 |
| `detail_ref` | 選択後にTool詳細を取得する参照 |

初期Catalog例:

* **Travel**: 家族の旅行記録、Trip、Experience、移動、メモを探して説明する
* **Photo**: 時期、場所、人物、イベントを基に写真を検索する
* **Memory**: 思い出、好み、過去の判断、重要な会話を深く参照する
* **Calendar**: 予定、登録、空き時間を扱う

当面は全Capability概要を毎Turn渡す。Pythonが発話から候補を絞ると、LLMは除外された能力の存在を
知らず、複数Capabilityの可能性も検討できない。規模拡大時は概要を短く保ち、LLM選択後に詳細だけ
段階提示する。semantic retrievalを将来使う場合も、全能力の発見可能性を失わないfallbackを持つ。

既存`skills/*/skill.json`はRuntime / UI向けSkill metadata、`tools/*/*.json`は実行契約であり、
Capability Catalogそのものではない。一つのCapabilityが複数Skill / Toolへ対応してもよく、一つの
Skillが複数Capabilityを提供してもよい。

Capability Usage RAGを将来追加する場合も、Catalogの正本性と全Capabilityを発見できるfallbackを
維持する。検索対象はSkillそのものではなく承認済みの「使い方」である。結果はCapability選択の
補助に限り、Action Toolのschema、risk、Permission、Confirmation、Auditを省略しない。

## Activation RAG candidates

Activation RAGはSQLite / Domain Repositoryの正本Entityを思い出すための再生成可能な索引である。
DBやRuntimeの代替ではなく、Entity Resolutionへ候補を渡す。現在発話と必要最小限のWorking Contextを
queryとして薄く検索する。

* 検索前に認証主体、owner、visibility、利用目的でfilterする
* 上位3〜5件、Provider、Entity参照、score、reason、更新時刻だけを基本とする
* Promptでは「関連する可能性がある候補。正本でもEvidenceでもない」と明記する
* 低score、矛盾、失効、Forget済み候補は渡さない
* 子ども、健康、位置、写真、予定などはより厳しい利用Policyを適用する
* 選択後はRepository / Runtime経由で正本を取得し、Evidenceを組み立て直す

Travelは最初のProvider / PoCである。Photo、Calendar、Memory Providerは将来追加し、HomeはActionなので
RAG Provider対象外とする。Memory Provider追加後もMemoryの作成、修正、共有、Forgetは別のguarded
writeであり、自動実行しない。

## Evidence Assembly

Tool結果は生JSONのまま最終LLMへ渡さない。Adapterがprovenanceを保ったEvidenceへ変換し、Coreが
共通形式へ組み立てる。Evidenceには少なくともCapability、Tool、対象Entity、取得時刻、source、
権限scope、結果または要約を持たせる。

最終回答は取得済みEvidenceの範囲を越えてユーザー固有の事実を作らない。一般知識による説明と
Evidence由来の主張を区別する。Evidence不足、競合、曖昧性が残る場合はclarificationへ戻る。

現行Travel v0.1では、一覧要求だけ`get_trips`全件をFinal Answerへ渡す。名前解決後は全件を捨て、
選択されたTripの`relevant_items`とtimelineなど最終Tool結果を中心にする。曖昧な場合はResolverが
返した候補だけを`clarification_candidates`として渡す。provenance、Tool ID、Skill IDは内部契約と
debugに保持するが、ユーザー向け本文の生成はFinal Answer LLMが担う。

## Budget and observability

sectionごとのtoken上限、採用件数、切り詰め理由を診断可能にする。優先順位はSystem / safety、
現在発話、認可済みUser Profile、Working Context、関連Activation候補、Capability概要、補助Current Worldの
順を基本とする。生の思考過程、秘密、Memory本文全量をdiagnosticsやauditへ残さない。

品質評価は少なくともBasic Chat、文脈継続、Memory誤想起、Capability選択、不要Tool抑制、権限漏えい、
Evidence groundingを分ける。

## Current gap and non-goals

現在の`POST /api/chat`は単一LLM Agent Loopと最大5TurnのConversation Stateを使う。Conversation Context
Builderの最小実装は接続済みだが、Current World、Memory Provider、永続Conversation State、section別budget、
完全な共通Turn契約は未実装である。

本実装はDB、Memory検索、意味要約、Capability検索を追加しない。
