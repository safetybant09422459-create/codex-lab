# Travel Chat Eval Harness v0.1

Travel Chat Eval Harnessは、固定質問を既存Chat Orchestratorへ通し、従来Runtimeのread結果を基準に会話品質を継続比較する開発者向けツールである。本番Chat APIの契約やBrowser挙動は変更しない。

## 評価経路

1. `evals/travel_chat_cases.json`から固定ケースを読む。
2. Runtimeの`get_trips`で基準Tripを取得する。
3. 文脈ケースでは`get_trip`、日程ケースでは`get_trip_timeline`もRuntimeから取得する。
4. `handle_travel_chat()`を実行する。Tool実行は通常のChat Tool PolicyとRuntimeを通る。
5. Tool、引数、返答、候補、navigation、更新文脈、debug stepを期待値と比較する。
6. `debug.steps`とTravelSearchIndexの再検索結果からReason Traceを生成する。
7. JSON summaryとMarkdown reportを出力する。

Chat／LLMがRuntimeを迂回する経路や、BrowserからOpenAI APIへ直接接続する経路は追加していない。

## 実行

既定のmockモードはケースファイル内の固定LLM proposalを使う。OpenAI APIを呼ばないため、通常テストとCIではこのモードを使う。

```bash
./.venv/bin/python -m backend.chat_eval
```

既定の出力先は`artifacts/chat_eval_summary.json`と`artifacts/chat_eval_report.md`である。失敗ケースがある場合、CLIは終了コード1を返す。現在のローカルRuntimeデータに期待Tripがない場合も、データ差分として失敗に記録される。

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
  "response_summary": {
    "action": "needs_context",
    "outcome": "candidates",
    "candidate_count": 2
  },
  "failure_category": null
}
```

- `planner`: mock時は固定proposal、live時はresponseから安全に確認できるTool情報を記録する。
- `runtime_steps`: Orchestratorの`debug.steps`を基に、件数など短いresult summaryを加える。
- `search_candidates`: Harnessが同じTravelSearchIndexを再実行した診断候補。`score`と`matched_by`は本番responseへ追加しない。
- `decision`: resolved、ambiguous、not_found、needs_context、errorなど最終判断を示す。
- `response_summary`: action、返答、候補件数を短くまとめる。
- `failure_category`: 成功時は`null`、失敗時は以下の分類となる。

## ケースと失敗カテゴリ

各ケースは`question`に加え、`expected_intent`、`expected_entity`、`expected_tool`、`expected_trip_title`、`expected_outcome`など必要な期待値を持つ。`requires_context`はRuntimeのTrip titleから信頼済みIDを解決する。`mock_proposal`はmockモード専用であり、期待値とは別に固定LLM出力を表す。

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

## 改善ループ

1. Evalをmock（必要な場合のみ明示的にlive）で実行する。
2. Summaryの失敗カテゴリ件数を見る。
3. Failure detailとReason TraceでPlanner、Runtime、検索候補、decisionを追う。
4. 原因に応じてSearchIndex / Planner / Context / Composerを改善する。
5. 再Evalし、固定10ケースと全テストの回帰を確認する。

Markdown末尾の改善ヒントはカテゴリ件数からルールベースで生成される。たとえば`entity_resolution_missing`は検索対象・expansion・score、`context_not_used`はConversationState / ContextReducerを優先候補として示す。

## テスト

```bash
./.venv/bin/python -m unittest tests.test_chat_eval -v
```

テストは固定Runtime fixtureと固定proposalを使用し、ネットワークやOpenAI APIを必要としない。

## 制約と安全性

v0.1はTravel read-only Toolだけを評価する。Harness自体はTripを更新しないが、Runtime readには通常の権限判定とauditが適用される。JSON／MarkdownにはChat返答、候補、旅行文脈が含まれるため、家族名、旅行先、日程などのプライバシー情報として保管先と共有範囲を制限する。credential形式は再帰的にredactするが、個人情報を匿名化する機能ではない。
