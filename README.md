# codex-lab
AI開発練習用

## Jarvis Dev v0.3

スマホブラウザから、このリポジトリ上の Jarvis Core / MCP / アプリ開発を進めるための AI 開発 PM ツールのプロトタイプ。

主要設計文書:

- [AI Coding Agent作業ガイド](AGENTS.md)
- [Turn Contract / Single Agent Loop Decision](docs/decisions/2026-07-turn-contract-single-agent-loop.md)
- [Jarvis Core LLM Contract Decision](docs/decisions/2026-07-llm-contract.md)
- [Jarvis vNext Single Agent Loop Architecture Decision](docs/decisions/2026-07-vnext-single-agent-loop-architecture.md)
- [Domain Provider Responsibility Boundary Decision](docs/decisions/2026-07-domain-provider-boundary.md)
- [Catalog Principle / Guardrail Decision](docs/decisions/2026-07-catalog-principle.md)
- [Conversation Quality / Python Brain Regression Guard Decision](docs/decisions/2026-07-conversation-quality-python-brain-regression-guard.md)
- [Observation Guardrail Decision](docs/decisions/2026-07-observation-guardrail.md)
- [Observation Reference Principle Decision](docs/decisions/2026-07-observation-reference-principle.md)
- [Long-term Context Principle Decision](docs/decisions/2026-07-long-term-context-principle.md)
- [Domain Provider Contract](docs/provider_contract.md)
- [Jarvis Chat Core / Orchestrator v2](docs/chat_core.md)
- [Jarvis Core Activation RAG](docs/activation_rag.md)
- [Context Assembly](docs/context_assembly.md)
- [Knowledge Enrichment](docs/knowledge_enrichment.md)
- [Conversation Quality Test](docs/conversation_quality_test.md)
- [Jarvis Simplification Phase](docs/jarvis_simplification_phase.md)

vNextの目標では、Webは複数Channelの一つであり、意味判断は単一のLLM Agent Loopへ集約する。
旧Router、Planner、Entity Resolver、Answer Generator等のTravel Chat互換コンポーネントは削除した。
Pythonは既存のRuntime、Skill / Domain Provider、Repository境界で決定的処理を担う。
Skillはユーザーから見える能力単位、Domain ProviderはCoreが利用する能力提供境界である。Providerは
MCP、REST API、Local Serviceへ交換可能で、ユーザー意図の解釈や最終回答を担わない。
Operation、Capability、Dashboard Catalogは宣言であり、発話routing、Operation選択、回答、表示優先順位を
持たない。これらの判断はLLM / Jarvis Coreが担う。

`tests/test_conversation_quality_smoke.py` のConversation Quality Smoke v0は、回答品質を評価する
Conversation Quality Testではない。Capability、Conversation Context、Observation、active entitiesがLLMへ
届くことだけを確認し、Pythonへ意味判断が戻ることを防ぐPython Brain Regression Guardである。

対象ディレクトリは固定で `/mnt/nas/projects/codex-lab`。
本番旅行アプリ `/mnt/nas/projects/project` は対象外。

### 起動方法

```bash
cd /mnt/nas/projects/codex-lab
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn openai
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

### 検証用Python

このリポジトリで FastAPI / TestClient / Runtime API を検証するときは、プロジェクトルートの通常の `python` ではなく、必ず仮想環境の `./.venv/bin/python` を使う。

```bash
cd /mnt/nas/projects/codex-lab
./.venv/bin/python scripts/check_runtime_api.py
```

スマホのブラウザで以下を開く。

```text
http://<ラズパイのIPアドレス>:8001
```

実運用では systemd service `jarvis-dev` として port `8001` で起動する。

アクセス例:

```text
http://<ラズパイのIPアドレス>:8001
```

### 現在の実装状態

Implemented:

- Skill Registry
- Tool Registry
- Runtime v0.1
- Audit Log v0.1
- Executor Registry v0.1
- Confirmation Engine v0.1
- Permission Engine v0.1
- Weather Executor v0.1 (`execution_mode: local_weather_stub`)
- Travel Runtime Read v0.1 (`execution_mode: local_travel_read`)
- Domain Provider / OperationContext最小契約
- TravelProvider（既存Travel Tool IDをOperation IDとして実行）
- Jarvis Status Provider（Provider-first経路の最初の明確な検証対象）
- Photo Provider read-only v0（Immichの最近の写真メタ情報。未設定時は安全なlimitationsを返す）
- Provider Contract v1 / Operation Catalog / Provider Registry
- Provider Operation Runtime API（既存Runtime safety layerへ委譲）
- LLMClient Interface / OpenAI AI Model Provider Adapter（Responses API structured output）
- Agent Host Single Agent Loop v0（LLMClient Interface経由、共通Turn開始、最大2step、LLM Action検証、Runtime Observation再入力、Trace）
- Activation RAG Travel Provider PoC（read-only候補想起。正本はSQLite / Repository）
- Agent Host経由のJarvis Chat v1最小経路（LLM → Runtime → Provider → Observation → LLM）
- FastAPI Chat API v0.1 (`POST /api/chat`)
- Conversation State v0（session単位のin-memory短期状態）
- Conversation Context Builder v0（StateからLLM Contextへの決定的な整形、制限、redaction、visibility filter）

Not Yet Implemented:

- Jarvis Chat Core / Orchestrator v2の完全版（Current World、Long-term Context、永続State、section別budget）
- Agent Hostの汎用的な複数Action反復、会話状態の永続化
- Long-term Context retrieval / 利用契約
- Knowledge Enrichment Engine
- Confirmation UI
- External API / DB-backed Real Tool Execution

`POST /api/chat`はAgent Hostに接続し、`LLMClient` InterfaceのOpenAI Adapterから共通Runtime / Provider
Operationを利用する。これはTravel Chat専用復旧ではなく、Jarvis Chat v1の最小経路である。
Capability Catalogの完成形、Long-term Context retrieval、複数Skill連携は未実装である。

### Conversation State v0

Conversation State v0は、同一プロセス内で`session_id`ごとに直近5ターンだけを保持する短期状態である。
保持対象はuser input、assistantの最終応答、直近LLM Action、直近Observation、LLMが返した
`active_entities`とObservation由来の正本ID付きEntity候補である。Entity Context v0ではTravelの
`get_trips`結果を`trip`候補として件数制限付きで保持する。次ターンのLLM Contract payloadへこれらを
渡すことで、「それ」「さっきの」
「続き」や直前のProvider結果をLLMが判断できるようにする。

Pythonは話題継続、参照解決、話題転換、Provider / Operation選択を行わず、履歴を解釈しない。
状態はprocess-local / short-term onlyで、再起動時に消える。DB、家族共有、Long-term Context、
write operationとの接続は含まない。Long-term Contextの実装方式は未決定である。

Jarvis Status Providerは、Travelより期待値が明確な最初のProvider-first検証用Providerである。
`jarvis.get_capabilities`、`jarvis.get_provider_status`、`jarvis.get_operation_catalog`をread-only / low-riskで
提供し、現在の能力、Provider状態、Operation Catalog要約を決定的な構造化データとして返す。Web Chatで
「何ができる？」「今使える機能は？」「プロバイダー一覧を教えて」と入力すると、LLMによるOperation選択から
Runtime、Jarvis Provider、Observation、LLMの自然文回答までの経路を確認できる。Providerはユーザー意図の解釈や
回答文生成を行わない。

`backend/agent_host.py`のAgent HostはSingle Agent Loop v0である。Agent Hostは`LLMClient` Interfaceだけに依存し、
composition rootの`backend/main.py`がOpenAI Adapterと共通Runtimeを注入して`/api/chat`へ接続する。
Fake LLM ClientはContract Test専用であり、意図判断や固定回答を追加して賢くしない。
最大2stepのObservation Loop（`call_operation -> Runtime -> Observation -> answer`）のみ実装済みである。

Photo Provider read-only v0は`photo.get_recent_photos`で最近の写真の件数、期間、位置・顔metadataの有無、
接続状態をObservation factsとして会話へ提供する。Immich未設定・接続失敗時は実在する写真を捏造せず、
`source: unavailable`とlimitationsを返す。Chatカード、サムネイル表示、Presentation Contractは未対応であり、
Presentation Contractを実装するまでは写真を表示しない。
1turnのOperation実行は最大1回であり、2step目は終端Actionでなければならない。2step目の
`call_operation`と、Catalog上で`planned`のOperation呼び出しは契約違反として実行前に拒否する。
`/api/chat`からはこの最大2stepの経路を使う。会話状態永続化、Confirmation再開、汎用的な反復は未実装である。

Activation RAGはTravel専用検索ではなく、Jarvis Coreが正本Entityを思い出すためのread-only索引である。
DBやRuntimeを置き換えず、Entity Resolutionへ未検証候補を渡す。Travelは最初のProvider / PoCであり、
Photo、CalendarとCapability Usage RAGは将来範囲、Home ActionはRAG対象外とする。Long-term Contextは
Domain Entityを探すActivation RAGとは別のLLM判断材料として扱う。
詳細は[Jarvis Core Activation RAG](docs/activation_rag.md)を参照する。

Travel Runtime Read v0.1 は実装済み。Runtime safety layer 経由で `backend/travel_executor.py` の `TravelExecutor` が呼ばれ、`backend/travel_repository.py` と `backend/travel_sources.py` のローカル読み取りデータを返す。

実装済み Travel Tool:

- `travel.get_trips` (`get_trips`)
- `travel.get_trip` (`get_trip`)
- `travel.get_trip_timeline` (`get_trip_timeline`)

`travel.get_spots` (`get_spots`) はTool定義のみ存在し、v0.1の実行対象外。現在は `TravelExecutor` の分岐、`TravelRepository` のメソッド、`TravelSource` のデータを持たない。

### 使い方

基本の流れは 開発 → レビュー → 更新。

1. 画面上部で Project 名、Local Path、Branch、Git 状態を確認する
2. ChatGPT 等で完成させた設計書や指示書を「開発」タブの Codex Prompt に貼り付ける
3. 「Codexへ送信」を押し、確認ダイアログで承認してから Codex を実行する
4. 「レビュー」タブで最終回答、tokens used、`git status`、変更ファイル、差分を確認する
5. 必要な場合だけ「レビュー」タブの Commit & Push を人間が明示操作する
6. 「更新」タブで `jarvis-dev` の systemd 状態を確認し、必要な場合だけ確認後に再起動する
7. Codex の生ログは「詳細ログ」タブで確認する

このアプリは Git commit / push を自動実行しない。Developer UIの `Commit & Push` を人間が押し、
backend preflightの結果を確認した場合だけ実行する。
Codex CLI には安全指示として、作業対象を `/mnt/nas/projects/codex-lab` に限定し、`/mnt/nas/projects/project` を触らないように伝える。
Codex CLI には `git commit` と `git push` を実行しないように伝える。

### タブ

- 「開発」: 完成した Codex Prompt を貼り付け、Codex 実行を開始
- 「レビュー」: 最終回答、tokens used、git status、変更ファイル、diff、Commit & Push
- 「更新」: `systemctl status jarvis-dev` と確認付きの非同期 restart 要求
- 「詳細ログ」: Codex の生ログ

相談チャット、ローカル下書きチャット、設計相談用の固定応答、「設計書テンプレを作る」ボタンは削除している。

### Git操作

Git 操作は Jarvis Dev backend APIだけが実行する。`GET /api/git/preflight` が差分とHEADを検査し、
Conventional Commits風メッセージを生成する。UIで確認した同一snapshotだけを
`POST /api/git/commit_push` がcommit/pushする。Codex実行中、diff check失敗、削除、secret候補、
`.env`、DB、media、symlink、1 MiB超、detached HEAD、upstream未設定の場合は停止する。
secret候補のpreflight結果は、ルール、ファイル、行番号、マスク済み検出文字列、対処方法を
構造化して返す。Developer UIではDiffを開く、Cancel、同一snapshotのsecret検出だけを明示確認付きで
一度無視する操作を提供する。検出した秘密情報そのものはAPI、UI、監査ログへ返さない。

### API

- `GET /api/project`
- `GET /api/skills`
- `GET /api/tools`
- `POST /api/run`
- `GET /api/logs`
- `GET /api/changes`
- `GET /api/diff?path=<path>`
- `GET /api/git/preflight`
- `POST /api/git/commit_push`
- `GET /api/service/status`
- `POST /api/service/restart`

Runtime API:

- `GET /api/runtime/tool/{tool_id}`
- `POST /api/runtime/validate`
- `POST /api/runtime/dry-run`
- `POST /api/runtime/execute`
- `GET /api/audit`
- `GET /api/providers/operations`
- `POST /api/runtime/operations/execute`

Chat API:

- `POST /api/chat`

`POST /api/chat` はWeb Chat入力を共通Agent Hostへ渡す。LLMが`answer`を返した場合は
Runtimeを呼ばず、`call_operation`を返した場合は共通RuntimeでOperationを実行し、Observationを
同じLLMへ戻して最終回答を得る。Travel専用Router / Planner / Entity Resolverは使わない。
BrowserへOpenAI API Keyを渡さず、BrowserからOpenAI APIへ直接接続しない。

Request:

```json
{
  "message": "旅行一覧を見せて",
  "session_id": "web-session-example",
  "debug": false
}
```

- `message`: ユーザーの発話
- `session_id`: 短期状態を分離するsession識別子。省略時はリクエスト単位となり文脈を引き継がない
- `role`: deprecated互換入力。指定されても無視する
- `debug`: 省略時は `false`。`true` の場合だけresponseへtimingを含める

成功Response例:

```json
{
  "action": "answer",
  "reply": "こんにちは。今日はどうしましたか？"
}
```

Travel Operationを含む手動確認:

```bash
curl -sS -X POST http://127.0.0.1:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"旅行一覧見せて","debug":true}' \
  | python -m json.tool
```

LLMの最終`answer`と、Runtime経由の`travel.get_trips`結果が返ることを確認する。

`POST /api/runtime/execute` は Runtime v0.1 の安全境界を通してToolを実行する。Weather は `local_weather_stub`、Travel read は `local_travel_read`、その他の未実装Toolは必要に応じて `stub` または planned として扱う。Travel read の成功実行もAudit Log対象で、現在の `event_type` は `runtime.execute_stub` のままだが、`execution_mode` には `local_travel_read` が記録される。

Permission Engine v0.1 はUIなし・認証なしで、request body の `role` だけを見る。未指定の場合は `guest` として扱う。role は `admin` / `family` / `guest` の3つで、`admin` は全Tool、`family` は read かつ low risk のTool、`guest` は read かつ low risk のToolだけを許可する。ただし `guest` は developer skill を実行できない。

Confirmation Engine v0.1 はUIなしで、`confirmed` フラグだけを見る。`risk_level: high` または `confirmation_required: true` のToolは、`confirmed: true` がない限りブロックされ、Audit Logに `runtime.confirmation_blocked` として記録される。

### 設定

Codex CLI が `codex` 以外のパスにある場合は `CODEX_BIN` を指定する。

```bash
CODEX_BIN=/path/to/codex uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

Codex CLI の引数を変えたい場合は `CODEX_ARGS` を指定する。
デフォルトは `exec`。

```bash
CODEX_ARGS="exec" uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

`/api/chat`で実LLMを利用するには`OPENAI_API_KEY`が必要である。未設定時はChat APIが
`503` と安全な設定エラーを返す。OpenAI疎通確認はサーバー側からのみ実行する。
プロジェクトルートの `.env` に
`OPENAI_API_KEY` と、必要に応じて `OPENAI_MODEL`（既定値は
`gpt-5.4-nano`）を設定してから実行する。API Keyをログやコマンドラインへ
出力しないこと。

Jarvis Agent Host向けには`OpenAIModelProviderAdapter`がResponses APIのstructured
outputで既存LLM Action schemaを要求し、返却Actionを同じschemaで再検証する。OpenAI固有処理は
Adapter内に閉じており、Agent Hostは`LLMClient` Interfaceだけに依存する。
`/api/chat`もこのInterface経由で実LLM Agent Loopを呼び出す。

Tool Proposal の推論設定は `.env` で変更できる。短いJSON提案を低レイテンシで
返す `gpt-5.4-mini` の推奨設定例は次のとおり。

```dotenv
OPENAI_MODEL=gpt-5.4-mini
OPENAI_REASONING_EFFORT=none
OPENAI_VERBOSITY=low
OPENAI_MAX_OUTPUT_TOKENS=256
OPENAI_TIMEOUT_SECONDS=30
```

- `OPENAI_REASONING_EFFORT`: Responses APIで指定可能な `none` / `minimal` /
  `low` / `medium` / `high` / `xhigh`（モデルごとに対応値は異なる）。
  `gpt-5.4-mini` は `none` / `low` / `medium` / `high` / `xhigh` に対応する。
  未設定ならリクエストへ含めず、モデルの公式デフォルトを使う。
- `OPENAI_VERBOSITY`: `low` / `medium` / `high`。未設定ならリクエストへ含めず、
  モデルの公式デフォルトを使う。
- `OPENAI_MAX_OUTPUT_TOKENS`: reasoning tokenを含む出力上限。既定値は `256`。
  Tool Proposalの短いJSONには十分な余裕を持たせつつ、過剰な生成を制限する。
- `OPENAI_TIMEOUT_SECONDS`: OpenAI API request timeout。正の数で指定し、既定値は`30`秒。

`temperature` と `top_p` は設定しておらず、APIのデフォルトを使う。設定変更後は
プロセスの再起動時に読み直される。OpenAI clientはプロセス内で遅延初期化して
再利用し、HTTP connection poolも後続リクエストで共有する。APIキーを変更した
場合、既存clientには反映されないため、FastAPIプロセスを再起動すること。
Uvicornを複数workerで起動した場合は、workerごとにclientが1つ作られる。

`gpt-5` で確認する場合は `.env` に `OPENAI_MODEL=gpt-5` を設定する。成功時は
モデルのテキストが返り、この疎通確認プロンプトで期待される表示は `OK`。
失敗時は `OpenAI connection failed:` に続いて、秘密情報を除いた原因が表示される。

```bash
./.venv/bin/python -c 'from backend.openai_adapter import check_openai_connection; print(repr(check_openai_connection()))'
```

期待結果（成功時）:

```text
'OK'
```

### 削除済み: Chat Orchestrator v0.1 / Runtime read実行

以下の節は旧設計の履歴であり、記載されたPython moduleと確認コマンドは現在存在しない。Travel Chat互換、
Planner v1、Python Entity解決は2026-07-05に削除した。復旧は旧moduleの復元ではなく、
[Domain Provider Contract](docs/provider_contract.md)を使う単一LLM Agent Loopで行う。

Chat Core v0.2 Foundationの責務、型、contextとroleの信頼境界は
[docs/chat_core.md](docs/chat_core.md)を参照する。Conversation State / Entity Resolution /
Plan Execute / Response Composerの4層を定義したが、公開APIは移行期間中のため従来形式を
維持している。Skill接続ではなくSkill連携を目標とし、Skill固有処理をChat Skill Adapterへ
委譲する判断は
[Chat Core Skill Adapter Architecture](docs/decisions/2026-06-chat-core-skill-adapter-architecture.md)
に記録している。

Travel内で「Tool結果を表示するだけでなく、質問へ直接答える」実装、Effort Policy、
Travel Answer Generator v0.1の責務は
[Chat Core v0.3: Response Intelligence](docs/chat_response_intelligence.md)に記録している。

`backend.chat_orchestrator.propose_travel_tool` は、ユーザーの自然文を
サーバー側からOpenAI Responses APIへ送り、Travel Toolの提案JSONを返す。
BrowserからOpenAIへ直接接続せず、この段階ではRuntimeやToolを実行しない。
レスポンスはサーバー側でJSON parse、allowlist、引数、型を検証し、不正な応答は
`needs_context` へ安全にfallbackする。OpenAIリクエストは `store=False` のままで、
会話や提案をAudit Logへ記録しない。

`backend.chat_orchestrator.handle_travel_chat` は同じproposal検証後、read-only
allowlistのToolだけを既存Runtime経由で実行する。`/api/chat`の`role`はserver側の
暫定`admin`に固定し、BrowserやLLMの値から採用しない。`confirmed=False`も
サーバー側で渡す。`update_experience` はproposalのみ許可し、
Runtime実行せず `pending_write_not_implemented` を返す。Runtime結果を再度LLMへは
送信しない。

Chat v0.1 allowlist:

- `get_trips`
- `get_trip`
- `get_trip_timeline`
- `get_experience`
- `get_experience_photos`
- `get_experience_photo_links`
- `get_experience_photo_search`
- `update_experience`（提案のみ。引数は `experience_id` と `memo` のみ）

サーバー側での手動確認:

```bash
./.venv/bin/python -c 'from backend.chat_orchestrator import propose_travel_tool; import json; print(json.dumps(propose_travel_tool("旅行一覧を見せて"), ensure_ascii=False, indent=2))'
```

proposalからRuntime read実行までの手動確認:

```bash
./.venv/bin/python - <<'EOF'
from backend.chat_orchestrator import handle_travel_chat
import json
print(json.dumps(handle_travel_chat("旅行一覧を見せて", role="admin", debug=True), ensure_ascii=False, indent=2))
EOF
```

期待結果は `action: "tool_result"`、`tool_id: "get_trips"` となり、`result` に
Travel一覧が入る。debug timingには `proposal_total`、`runtime_execute`、`total` が
含まれる。

FastAPI Chat APIの手動確認（起動中のserviceへコード変更を反映してから実行）:

```bash
curl -sS -X POST http://127.0.0.1:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"旅行一覧を見せて","debug":true}' \
  | python -m json.tool
```

通常の返却形式を変えずに処理時間を確認する場合は `debug=True` を指定する。
`build_prompt`、`llm_call`、`json_parse`、`policy_validation`、`fallback`、
`total` がミリ秒で返る。実OpenAI Adapterを使った場合は、Adapter内の
`api_call`、`response_text_extraction`、`total` も返る。debug情報にAPIキー、
リクエスト本文、レスポンス本文、例外本文は含まれない。

```bash
./.venv/bin/python -c 'from backend.chat_orchestrator import propose_travel_tool; import json; print(json.dumps(propose_travel_tool("旅行一覧を見せて", debug=True), ensure_ascii=False, indent=2))'
```

Python起動を含むプロセス全体の時間は、同じコマンドを `/usr/bin/time` で囲んで
確認する。`elapsed` と debug の `total` の差には、Python起動、import、終了処理などが
含まれる。

単発CLI実行では、毎回新しいPythonプロセスでOpenAI clientの初期化と初回接続を
行うため遅く見える。FastAPIの常駐プロセスではclientとHTTP接続が再利用されるため、
同一プロセスで計測した2回目以降の速度に近づく。ただし、ネットワークやモデル側の
待ち時間はリクエストごとに変動する。

```bash
/usr/bin/time -f 'elapsed=%e sec' ./.venv/bin/python -c 'from backend.chat_orchestrator import propose_travel_tool; propose_travel_tool("旅行一覧を見せて", debug=True)'
```

常駐プロセス相当のwarm-upと後続2回を確認する場合:

```bash
./.venv/bin/python - <<'EOF'
from backend.chat_orchestrator import propose_travel_tool
import json
import time

for i in range(3):
    t0 = time.perf_counter()
    result = propose_travel_tool("おはよう", debug=True)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"\n--- run {i+1} outer_ms={elapsed:.3f} ---")
    print(json.dumps(result["debug"], ensure_ascii=False, indent=2))
EOF
```

テスト:

```bash
./.venv/bin/python -m unittest tests.test_chat_orchestrator tests.test_openai_adapter -v
```

## 運用前チェック

目的は、Raspberry Pi 故障時でも GitHub から 10 分以内に復旧できる状態を保つこと。

### 環境情報

- 実行環境: Raspberry Pi 4
- Python: 仮想環境 `.venv` を使用
- systemd サービス名: `jarvis-dev`
- 待受ポート: `8001`
- GitHub リポジトリURL: `git@github.com:safetybant09422459-create/codex-lab.git`

### 新規セットアップ手順

空の Raspberry Pi から復旧する場合は、GitHub からリポジトリを取得して Python 仮想環境、依存パッケージ、systemd サービスを再作成する。

```bash
cd /mnt/nas/projects
git clone git@github.com:safetybant09422459-create/codex-lab.git
cd /mnt/nas/projects/codex-lab
```

Python 仮想環境を作成し、依存パッケージをインストールする。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn openai
```

手動で起動確認する。

```bash
cd /mnt/nas/projects/codex-lab
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

スマホまたはPCのブラウザで以下を開く。

```text
http://<ラズパイのIPアドレス>:8001
```

systemd サービスを作成する。

```bash
sudo nano /etc/systemd/system/jarvis-dev.service
```

設定例:

```ini
[Unit]
Description=Jarvis Dev
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/mnt/nas/projects/codex-lab
Environment="PATH=/mnt/nas/projects/codex-lab/.venv/bin:/usr/local/bin:/usr/bin:/bin:/home/pi/.local/bin:/home/pi/.npm-global/bin"
Environment="CODEX_ARGS=exec"
ExecStart=/mnt/nas/projects/codex-lab/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

サービスを有効化して起動する。

```bash
sudo systemctl daemon-reload
sudo systemctl enable jarvis-dev
sudo systemctl start jarvis-dev
sudo systemctl status jarvis-dev
```

Jarvis Dev の Web UI から `jarvis-dev` だけを再起動できるように、sudoers を設定する。

```bash
sudo visudo -f /etc/sudoers.d/jarvis-dev
```

設定例:

```sudoers
pi ALL=(root) NOPASSWD: /usr/bin/systemctl restart jarvis-dev
```

`systemctl` のパスが異なる場合は `command -v systemctl` で確認し、sudoers のパスを合わせる。
状態確認 API は sudo を使わず、`systemctl status jarvis-dev` を実行する。
再起動 API は HTTP 応答中に Jarvis Dev 自身が終了しないよう、`bash -lc` から `nohup bash -c 'sleep 2; sudo systemctl restart jarvis-dev; ...' &` を起動して即時応答する。
API の応答には、遅延 restart を予約したコマンド、return code、stdout、stderr が含まれる。
実際の restart は 2 秒後にバックグラウンドで実行され、実行時の stderr と return code は `/tmp/jarvis-dev-restart.log` に出力される。
予約コマンドが失敗した場合、画面には `ok=false` 相当の失敗状態と `command` / `return code` / `output` / `stderr` が表示される。
Web UI は restart 要求後も自動リロードせず、Service Status の定期監視を続ける。Jarvis Dev が再起動後に応答を返すようになったら、状態表示は `running` に戻る。

### 運用コマンド

状態確認:

```bash
sudo systemctl status jarvis-dev
```

再起動:

```bash
sudo systemctl restart jarvis-dev
```

ログ確認:

```bash
journalctl -u jarvis-dev -n 100
```

Git 更新:

```bash
cd /mnt/nas/projects/codex-lab
git pull
```

Git 反映:

```bash
cd /mnt/nas/projects/codex-lab
git push
```

### 障害対応

#### Web画面が開かない

サービス状態、ログ、待受ポート、プロセスを確認する。

```bash
sudo systemctl status jarvis-dev
journalctl -u jarvis-dev -n 100
ss -ltnp | grep 8001
ps aux | grep uvicorn
```

手動起動でエラー内容を確認する。

```bash
cd /mnt/nas/projects/codex-lab
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

#### Codex CLIが見つからない

Codex CLI と Node.js の場所を確認する。

```bash
which codex
which node
```

systemd から見えない場合は、`/etc/systemd/system/jarvis-dev.service` の `PATH` に `codex` と `node` があるディレクトリを追加する。

```ini
Environment="PATH=/mnt/nas/projects/codex-lab/.venv/bin:/usr/local/bin:/usr/bin:/bin:/home/pi/.local/bin:/home/pi/.npm-global/bin"
```

設定変更後に再読み込みして再起動する。

```bash
sudo systemctl daemon-reload
sudo systemctl restart jarvis-dev
sudo systemctl status jarvis-dev
```

#### GitHubへPushできない

SSH 鍵と GitHub 接続を確認する。

```bash
ls ~/.ssh
ssh -T git@github.com
```

remote URL を確認する。

```bash
cd /mnt/nas/projects/codex-lab
git remote -v
```

`Permission denied (publickey)` が出る場合は、Raspberry Pi の公開鍵を GitHub に登録する。

### バックアップ方針

GitHub を正とする。

Raspberry Pi 故障時は、GitHub リポジトリから `git clone` して復元可能な状態にする。
ローカルだけに存在する変更を残さないように、運用完了時は必要な変更を GitHub に反映する。
