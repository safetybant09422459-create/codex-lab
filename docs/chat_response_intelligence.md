# Chat Core v0.3: Response Intelligence

## Status

この文書はResponse Intelligenceの設計と実装済み範囲を記録する。Travel Answer Generator v0.1と
Planner v2 Goal-aware Planningは、既存APIとRuntime境界を保ったままTravelの読み取り質問を
縦に通している。

ただし、この実装はTravel Capability内のResponse Intelligenceであり、Jarvis全体の会話入口ではない。
Orchestrator v2では、Basic ChatとCapability選択の後にTravelが選ばれた場合だけ本フローを使う。
全TurnをGoal-aware Planningへ通さず、Travel Planner / Answer GeneratorはTravel Skill Adapter側へ
位置づける。上位方針は[Jarvis Chat Core / Orchestrator v2](chat_core.md)を参照する。

## 原則

Jarvisの目的はToolを実行することではなく、ユーザーの質問に答えることである。
Tool実行は回答に必要なEvidenceを集める手段であり、「タイムラインを取得しました」のような
実行報告だけを最終回答にしない。

例えば次のように、取得結果から質問に必要な部分を選んで答える。

* 「神戸の旅行で何食べた？」では、対象旅行を特定してtimelineやexperienceを読み、食べ物に
  関係する記録だけを答える。
* 「まいの初旅行って何した？」では、対象旅行を特定してtimelineを時系列に要約する。
* 「2日目何した？」では、会話中の旅行と2日目を解決し、その日の記録だけを答える。

このため、Planner、Entity Resolver、Plan Executor、Runtime、Response Composerに加えて、
質問と取得済みEvidenceから直接回答を作るAnswer Generatorを導入する。

## 責務と呼び出し順

```text
User question
    -> Planner                 # 回答目的と必要なEvidenceを計画
    -> Plan Executor           # Resolverを調整し、read Toolを選択
    -> Runtime                 # Permission / Confirmation / Auditを維持して実行
    -> Answer Generator        # 与えられたEvidenceだけで質問へ回答
    -> Response Composer       # API互換response / content block / actionへ整形
```

Entity ResolverはExecutorから呼ばれ、対象旅行を確定する。Answer GeneratorはExecutor成功後、
Composer前に置く。Answer GeneratorとComposerの責務は分ける。

* Answer Generator: 質問への直接回答、Evidenceの選択と要約
* Response Composer: outcome、legacy API形式、content block、suggested action、会話状態の整形

Answer GeneratorはRuntime、Repository、Tool、Resolverを呼ばない。入力として渡されたEvidence
だけで回答し、Evidenceにない事実を補わない。追加Toolが必要かどうかの判断は、将来の
Evaluator / Replannerへ分離する。不足や曖昧さを解消できない場合は、推測せず聞き返す。

## Effort Policy

質問の難易度と利用可能なSkillに応じて、LLMとToolの探索量を制限する。簡単な質問へ毎回深い
LLMループを使わない。

| Effort | LLM上限 | Tool上限 | 方針 |
| --- | ---: | ---: | --- |
| Easy | 1回 | 0〜1回 | replanなし。既知の文脈または単一Evidenceで回答する |
| Medium | 最大2回 | 最大2回 | Plannerと回答生成を許可する。v0.1のTravel回答は原則ここに収める |
| Hard | 最大3回 | 最大4回 | 複数Evidenceを扱う。Adaptive Replanは将来追加する |

全Effortに次の制約を適用する。

* 同じToolと同じ正規化済み引数の組み合わせを、同一リクエスト内で再実行しない。
* write系Toolは探索ループの対象外とし、従来どおりRuntimeの確認境界へ渡す。
* 上限へ達した場合や対象・日付を一意に決められない場合は、推測せず聞き返す。
* LLM回数とTool回数をdebug diagnosticsへ残し、上限をテスト可能にする。

## Travel Answer Generator v0.1 Scope

v0.1はTravelのread-only質問だけを対象にし、追加探索、Evaluator、Replannerは実装しない。

Planner v2では`Plan.goal / answer_mode / required_evidence`をAnswer Generatorまで保持する。
Generatorは質問文の再分類より`answer_mode`を優先し、`summary`は全timeline、`day_summary`は
指定日、`meals`は食事Evidenceだけを回答する。Evidenceがない場合は推測せず、特に食事では
「取得できた情報には食事内容は含まれていません」と返す。

現在発話のGoal判定はPlanner LLMへ任せ、Pythonは許可されたGoal tupleの検証と正規化だけを行う。
LLM失敗時は語彙推定をせず`needs_context`へ安全に倒し、不正な出力をTool実行へ昇格させない。
Photo Goalは
`show_photos / photos / [trip, experience, photo]`として保持し、Photo本格連携なしに写真取得を
装わない。

対象質問は次の3種類とする。

* 「○○旅行って何した？」: timeline全体の要約
* 「○○旅行で何食べた？」: timeline / experienceの食事関連記録の抽出
* 「○日目何した？」: 選択中旅行の指定日の要約

基本フローは「旅行特定 → timeline取得 → Answer Generatorによる自然文回答」とする。
現実装のLLM呼び出しはPlannerの最大1回で、Answer Generatorは取得済みEvidenceを決定的に整形する。
Toolは、名前付き
質問では`get_trips → get_trip_timeline`、選択中旅行では必要に応じて
`get_trip → get_trip_timeline`の最大2回を想定する。

名前付き質問ではPlanの回答目的と必要Evidenceに従い、旅行解決後に
`get_trip`または`get_trip_timeline`へ進む。

### 最小契約案

共通型は`backend/chat_core.py`、Travel固有実装は新規
`backend/travel_answer_generator.py`へ置く。

```text
AnswerGenerationRequest
  question
  answer_goal             # trip_summary / food_summary / day_summary
  resolved_entities
  evidence[]              # Runtime取得済み、出所付き、redaction対象
  constraints             # day、言語、出力上限など

AnswerGenerationResult
  status                  # answered / insufficient_evidence / needs_clarification
  answer
  evidence_refs[]         # 回答に使用したEvidence識別子
  diagnostics             # LLM回数など。秘密や生の思考過程は含めない
```

`AnswerGenerator.generate(request)`は純粋な生成境界とし、Runtimeへ到達できる依存を渡さない。
OpenAIを使う場合もBrowserではなく既存server-side adapterから呼び、将来Providerを差し替えられる
呼び出し契約を保つ。LLM失敗時は事実を捏造せず、既存の安全なComposer応答または聞き返しへ
fallbackする。

### 実装時に触るファイル

* `backend/chat_core.py`: Answer Generatorの共通Request / Result / ProtocolとEvidence型
* `backend/travel_answer_generator.py`: Travel v0.1のprompt、Evidence整形、出力検証
* `backend/travel_planner.py`: 回答目的と必要Evidenceを検証済みPlanへ保持
* `backend/travel_plan_executor.py`: 解決後のtimeline取得、Tool重複防止、Effort上限
* `backend/chat_orchestrator.py`: Executor後・Composer前へのGenerator接続と合計回数の計測
* `backend/travel_response_composer.py`: 生成済み回答をlegacy `reply`とV1 messageへ反映
* `tests/test_travel_answer_generator.py`: grounding、食事抽出、日別抽出、不足Evidence、LLM失敗
* `tests/test_chat_orchestrator.py`: 最大2 LLM / 最大2 Tool、Runtime経由、API互換、重複禁止
* `tests/test_travel_response_composer.py`: 生成回答と既存result / navigationの互換
* `evals/travel_chat_cases.json`と`backend/chat_eval.py`: Tool選択だけでなく回答内容の評価

最初の実装では`result`など既存レスポンスフィールドを削除せず、`reply`を直接回答へ改善する。
公開APIを`ChatResponseV1`へ切り替える作業は別フェーズとする。

## 実装リスク

* PlannerのTool提案だけでは回答目的が失われるため、Plan契約を後方互換で拡張する必要がある。
* Timeline Itemの表現揺れから食事を抽出する際、Evidenceにない料理名をLLMが補う危険がある。
  promptだけでなくEvidence参照と評価ケースでgroundingを検証する。
* 「○日目」の日付計算はTrip開始日、Itemのtimezone、欠損日時を一貫して扱う必要がある。
* Runtime結果には家族の行動、場所、メモが含まれる。必要最小限のEvidenceだけをLLMへ渡し、
  secret redaction、権限、監査境界を維持する。
* PlannerまたはAnswer Generator失敗時のfallbackで、現在のAPI shapeや候補選択を壊さない。
* LLM回数だけでなく、Resolver内部を含む実Tool実行回数を一つの予算として数える必要がある。

## Future

v0.1の次に以下を検討する。

* Evaluator: 回答が質問へ答え、Evidenceにgroundedしているかを評価する。
* Adaptive Replan: Evidence不足時だけ、残予算内で追加探索する。
* Skill増加時の探索方針: SkillごとのEvidence capabilityとcostを登録し、難易度に応じて選ぶ。
* Photo / Calendar / Garden: 同じAnswer Generator契約へ各SkillのEvidenceを渡す。
* 付加価値提案: 「写真も見ますか？」「この旅行の振り返りを作りますか？」
  「次回似た旅行プランを作れます」のような候補を`SuggestedAction`として提示する。

付加価値提案は質問への回答後に追加し、回答の代わりにしない。閲覧提案と更新提案を区別し、
更新を伴う操作は必ずRuntimeのPermission / Confirmation / Audit境界を通す。

## 設計制約

* Answer GeneratorはRuntimeを呼ばず、与えられたEvidenceだけで答える。
* 追加Toolの判断は将来のEvaluator / Replannerへ分離する。
* Permission / Confirmation / Auditは現在のRuntime境界を維持する。
* BrowserからOpenAI APIへ直接接続せず、Runtimeも迂回しない。
* 既存`POST /api/chat`のAPI互換を壊さない。
* UIのDOMや画面遷移をAnswer Generatorへ持ち込まない。
