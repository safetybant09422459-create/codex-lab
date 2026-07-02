# Jarvis Benchmark v0.3

> Router、Planner、Answer Generator等の統合・削除後も、返答文ではなく責務、安全、根拠、Capability品質を
> 継続評価する上位方針は[Conversation Quality Test](conversation_quality_test.md)を参照する。本書のBenchmarkは
> 現行Travel実装を診断する既存基盤であり、Conversation Quality Test全体の実装を意味しない。

Jarvis Benchmarkは、固定質問を既存Chat Orchestratorへ通し、従来Runtimeのread結果を基準に会話品質を継続比較する開発者向け評価基盤である。PASS/FAILだけでなく失敗レイヤーとRoot Causeを定量化し、次に改善する場所を決める。本番Chat APIの契約やBrowser挙動は変更しない。

Benchmark Versionは`Jarvis Benchmark v0.3`である。v0.2までのJSONフィールドを維持したままRoot Cause分析フィールドを追加する。

## 評価経路

1. `evals/travel_chat_cases.json`から固定ケースを読む。
2. Runtimeの`get_trips`で基準Tripを取得する。
3. 文脈ケースでは`get_trip`、日程ケースでは`get_trip_timeline`もRuntimeから取得する。
4. `handle_travel_chat()`を実行する。Tool実行は通常のChat Tool PolicyとRuntimeを通る。
5. Tool、引数、返答、候補、navigation、更新文脈、debug stepを期待値と比較する。
6. `debug.steps`とTravelSearchIndexの再検索結果からReason Traceを生成する。
7. clarification responseでは`clarification_layer`をReason Traceへ記録する。
8. failure categoryを単一のfailure layerへ写像し、固定ルールでimprovement hintを生成する。
9. expected、actual、候補、質問、Reason Traceから失敗のRoot Causeを固定ルールで分類する。
10. Skill別のLayer Summary、Root Cause Summary、Improvement Opportunities、Executive Summaryを含むJSON／Markdown reportを出力する。
11. 必要に応じて結果全体をbaselineとして保存し、過去結果との差分とRegressionを検出する。

Chat／LLMがRuntimeを迂回する経路や、BrowserからOpenAI APIへ直接接続する経路は追加していない。

## 実行

既定のmockモードはケースファイル内の固定LLM proposalを使う。OpenAI APIを呼ばないため、通常テストとCIではこのモードを使う。

```bash
./.venv/bin/python -m backend.chat_eval
```

既定の出力先は`artifacts/chat_eval_summary.json`と`artifacts/chat_eval_report.md`である。失敗ケースがある場合、CLIは終了コード1を返す。現在のローカルRuntimeデータに期待Tripがない場合も、データ差分として失敗に記録される。ケースには現状の弱点を可視化する意図的な未達期待値も含むため、mockモードの終了コード1は必ずしもHarness異常を意味しない。

liveモードは明示指定した場合だけserver-side adapterからOpenAI modelを呼ぶ。API課金、外部送信、API key、利用modelを確認し、CIでは有効にしない。

```bash
./.venv/bin/python -m backend.chat_eval --mode live
```

出力先、ケースファイル、単一出力形式を指定できる。

```bash
./.venv/bin/python -m backend.chat_eval \
  --cases evals/travel_chat_cases.json \
  --json-output /tmp/chat-eval.json \
  --markdown-output /tmp/chat-eval.md

./.venv/bin/python -m backend.chat_eval --format json
./.venv/bin/python -m backend.chat_eval \
  --format markdown --output /tmp/chat-eval.md
```

baselineを保存する場合は`--save-baseline`を使う。パスを省略した場合は作業ディレクトリの`baseline.json`へ保存する。

```bash
./.venv/bin/python -m backend.chat_eval --save-baseline
./.venv/bin/python -m backend.chat_eval \
  --save-baseline artifacts/baseline.json
```

2つのBenchmark JSONを比較する場合は`--diff`を使う。Layerの差分は`baselineの失敗件数 - currentの失敗件数`であり、正が改善、負が悪化を表す。Overallは合格率のpercentage point差である。悪化したLayerがある場合はRegressionを表示し、CLIは終了コード1を返す。

```bash
./.venv/bin/python -m backend.chat_eval \
  --diff benchmark_a.json benchmark_b.json

./.venv/bin/python -m backend.chat_eval \
  --diff benchmark_a.json benchmark_b.json \
  --format json --output artifacts/benchmark_diff.json
```

## Reason Traceの読み方

各ケースの`trace`は次の構造を持つ。これは評価用diagnosticsであり、本番Chat responseの仕様は変更しない。

```json
{
  "question": "神戸旅行を開いて",
  "planner": {
    "proposed_tool": "get_trips",
    "proposed_arguments": {},
    "confidence": "medium"
  },
  "runtime_steps": [
    {"step": 1, "tool_id": "get_trips", "result_summary": "trips=7"}
  ],
  "search_candidates": [
    {
      "title": "須磨シーワールド",
      "score": 0.72,
      "matched_by": ["query_expansion:title"],
      "prefectures": "兵庫県"
    }
  ],
  "decision": {"type": "ambiguous", "reason": "multiple_candidates"},
  "clarification_layer": {
    "status": "candidates",
    "reason": "multiple_candidates",
    "recommended_action": "select_candidate"
  },
  "response_summary": {
    "action": "needs_context",
    "outcome": "candidates",
    "candidate_count": 2
  },
  "failure_category": null,
  "failure_layer": null,
  "failure_root_cause": null,
  "improvement_hint": null
}
```

- `planner`: mock時は固定proposal、live時はresponseから安全に確認できるTool情報を記録する。
- `runtime_steps`: Orchestratorの`debug.steps`を基に、件数など短いresult summaryを加える。
- `search_candidates`: Harnessが同じTravelSearchIndexを再実行した診断候補。`score`と`matched_by`は本番responseへ追加しない。
- `decision`: resolved、ambiguous、not_found、needs_context、errorなど最終判断を示す。
- `clarification_layer`: clarification時のstatus、候補件数、理由、推奨する次の操作を示す。候補本体は既存の`candidates`に保持し、非clarification時は`null`。
- `response_summary`: action、返答、候補件数を短くまとめる。
- `failure_category`: 成功時は`null`、失敗時は以下の分類となる。
- `failure_layer`: 成功時は`null`。失敗時は改善責任を持つ単一レイヤーとなる。
- `failure_root_cause`: 成功時は`null`。失敗時は観測情報から判定した直接原因となる。
- `improvement_hint`: 成功時は`null`。失敗レイヤーに対応する固定の改善候補となる。

## ケースと失敗カテゴリ

各ケースは`question`に加え、`expected_intent`、`expected_entity`、`expected_tool`、`expected_trip_title`、`expected_outcome`など必要な期待値を持つ。`requires_context`はRuntimeのTrip titleから信頼済みIDを解決する。任意の`conversation_history`はPlannerへ渡す直近のWorking Contextを表す。`mock_proposal`はmockモード専用であり、期待値とは別に固定LLM出力を表す。

現在は54ケースで、検索語の種類と会話状態を次の8分類で覆う。`expected_classification`はケース分類を表し、未対応ケースでは既存の判定値`unsupported_or_needs_experience_context`も兼ねる。

| ケース分類 | `expected_classification` | 件数 |
| --- | --- | ---: |
| Trip title / partial title | `trip_title_or_partial_title` | 10 |
| prefecture / location | `prefecture_or_location` | 8 |
| memo由来 | `memo_derived` | 8 |
| date / year / duration | `date_year_or_duration` | 8 |
| context follow-up | `context_follow_up` | 7 |
| Travel answer generation | `travel_answer_generation` | 4 |
| ambiguous query | `ambiguous_query` | 5 |
| unsupported query | `unsupported_or_needs_experience_context` | 4 |

単一Tripを期待するケースは`expected_tool`と`expected_trip_title`、複数候補を期待するケースは`expected_outcome: candidates`と`expected_contains_titles`、会話状態を使うケースは`requires_context`を設定する。未対応ケースはToolを期待せず、`expected_outcome: unsupported`を設定する。

JSONの`failure_categories`には0件を含む全カテゴリの件数が入る。

- `tool_selection_error`: Plannerが期待Toolを選んでいない。
- `entity_resolution_missing`: 対象entityを検索・解決できない。
- `entity_resolution_ambiguous`: 候補を一意に絞れない。
- `wrong_entity`: 別entityを選択、または期待候補を返していない。
- `context_not_used`: 選択済み旅行など会話文脈が適用されていない。
- `response_not_human_friendly`: 人向けの返答が空、または不正である。
- `unsupported_expected`: 未対応として扱うべきintentを実行した。
- `runtime_error`: Runtime実行またはHarness内Chat呼び出しが失敗した。
- `security_violation`: 未redactのcredentialらしき値を検出した。

## Failure LayerとSkill集計

カテゴリは観測した失敗状態、レイヤーは改善対象を表す。現在の固定写像は次の通りである。未知のカテゴリは`unknown`へ集約し、集計漏れを防ぐ。

| Failure category | Failure layer |
| --- | --- |
| `tool_selection_error` | `tool_selection` |
| `entity_resolution_missing`, `entity_resolution_ambiguous` | `entity_resolution` |
| `wrong_entity` | `search` |
| `context_not_used` | `context` |
| `response_not_human_friendly` | `response` |
| `unsupported_expected` | `planner` |
| `runtime_error` | `tool_execution` |
| `security_violation` | `unknown` |

全ケースは`skill_id`を持つ。未指定時は現在の既定値`travel`を使う。JSONの`layer_summary`は`skill_id -> failure_layer -> count`である。MarkdownもSkillごとにLayer Summaryを分ける。このためPhoto、Garden、Calendar、Memoryのケースは、同じHarnessへ`skill_id`付きで追加できる。

## Failure Root Cause

Root Cause分類は`query_too_broad`、`missing_semantic_match`、`missing_memo_paraphrase`、`missing_experience_search`、`ambiguous_expected_but_resolved`、`context_slot_missing`、`benchmark_expectation_mismatch`、`unsupported_intent`、`unknown`である。分類はReason Trace、expected、actual、candidates、questionだけを使う決定的ルールであり、Chat本体の判定には影響しない。

`root_cause_summary`は各原因の件数、代表質問（最大3件）、改善案、想定改善件数、難易度を持つ。`root_cause_opportunities`は件数順の改善候補、`recommended_next_actions`はその実行順を表す。MarkdownはFailure Analysis、Root Cause Summary、Top Root Causes、Failure Details、Recommended Next Actionsを出力する。

## Improvement Opportunitiesと優先度

`improvement_opportunities`は従来どおりSkill／Layer単位で出力し、`top_improvements`にも同じ内容を残す。v0.3ではRoot Cause単位の`root_cause_opportunities`も追加する。優先度は全体割合20%以上をHigh、10%以上をMedium、それ未満をLowとする。

## Benchmark DiffとRegression

DiffはSkill別集計をFailure Layer単位に合算し、baselineとcurrentを比較する。Layerの`delta`が正なら失敗減少、0なら不変、負なら失敗増加である。負のLayerを`regressions`へ列挙する。Planner、Search、Contextに限定せず全Layerへ同じ規則を適用する。

baselineは通常のBenchmark JSONと同じ完全な結果である。ケース内容、返答、旅行文脈を含むため、回帰比較に必要な範囲で保管しアクセス制御する。

## Executive Summary

Markdown冒頭のExecutive Summaryは、最大のOpportunity、その全体割合、Context／Plannerの安定状況、次に行う改善候補を決定的なルールで生成する。LLM要約ではないため、CIでも同じ入力から同じ文章になる。

## 改善ループ

1. Evalをmock（必要な場合のみ明示的にlive）で実行する。
2. Summaryの失敗カテゴリ件数を見る。
3. Root Cause Summary、Failure Details、Reason TraceでPlanner、Runtime、検索候補、decisionを追う。
4. 原因に応じてSearchIndex / Planner / Context / Composerを改善する。
5. 再Evalし、固定54ケースと全テストの回帰を確認する。

Conversation Working Context v0.1では、神戸の履歴と選択状態から大阪の明示質問へ対象変更するケースを追加した。54ケースのmock baselineは52 pass、2 failである。固定proposalを使うため、このbaselineが測るのは主にOrchestrator、Search Index、Working Context／Conversation State適用、Clarification Policyであり、LLM Planner自体の品質はliveモードで別途確認する。

Markdown末尾のImprovement OpportunitiesはSkill／Layerごとの件数順で生成される。たとえば`entity_resolution`はSearchDocumentの地域情報・別名・識別属性、`context`はConversationStateの解決済みEntity保持を改善候補として示す。これは優先順位決定用の診断であり、Benchmark実行自体は検索・Planner・Chat Coreを変更しない。

## テスト

```bash
./.venv/bin/python -m unittest tests.test_chat_eval -v
```

テストは固定Runtime fixtureと固定proposalを使用し、ネットワークやOpenAI APIを必要としない。

## 制約と安全性

v0.3はTravel read-only Toolだけを評価する。Harness自体はTripを更新しないが、Runtime readには通常の権限判定とauditが適用される。baseline、JSON、MarkdownにはChat返答、候補、旅行文脈が含まれるため、家族名、旅行先、日程などのプライバシー情報として保管先と共有範囲を制限する。credential形式は再帰的にredactするが、個人情報を匿名化する機能ではない。
