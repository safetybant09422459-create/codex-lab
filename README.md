# codex-lab
AI開発練習用

## Jarvis Dev v0.3

スマホブラウザから、このリポジトリ上の Jarvis Core / MCP / アプリ開発を進めるための AI 開発 PM ツールのプロトタイプ。

対象ディレクトリは固定で `/mnt/nas/projects/codex-lab`。
本番旅行アプリ `/mnt/nas/projects/project` は対象外。

### 起動方法

```bash
cd /mnt/nas/projects/codex-lab
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn
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

Not Yet Implemented:

- Confirmation UI
- External API / DB-backed Real Tool Execution

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
5. 必要な場合だけ「レビュー」タブの Commit / Push を人間が明示操作する
6. 「更新」タブで `jarvis-dev` の systemd 状態を確認し、必要な場合だけ確認後に再起動する
7. Codex の生ログは「詳細ログ」タブで確認する

このアプリは Git commit / push を自動実行しない。
Codex CLI には安全指示として、作業対象を `/mnt/nas/projects/codex-lab` に限定し、`/mnt/nas/projects/project` を触らないように伝える。
Codex CLI には `git commit` と `git push` を実行しないように伝える。

### タブ

- 「開発」: 完成した Codex Prompt を貼り付け、Codex 実行を開始
- 「レビュー」: 最終回答、tokens used、git status、変更ファイル、diff、Commit、Push
- 「更新」: `systemctl status jarvis-dev` と確認付きの非同期 restart 要求
- 「詳細ログ」: Codex の生ログ

相談チャット、ローカル下書きチャット、設計相談用の固定応答、「設計書テンプレを作る」ボタンは削除している。

### Git操作

Git 操作は Jarvis Dev 側の API だけが実行する。

- 「Commit」: コミットメッセージ入力欄の内容で `git add -A` と `git commit -m` を実行する
- 「Push」: 確認ダイアログ後、さらに `PUSH` と入力した場合だけ `git push` を実行する

Commit のデフォルトメッセージは `Update Jarvis Dev v0.3`。
ユーザーは画面上で編集できる。

### API

- `GET /api/project`
- `GET /api/skills`
- `GET /api/tools`
- `POST /api/run`
- `GET /api/logs`
- `GET /api/changes`
- `GET /api/diff?path=<path>`
- `POST /api/commit`
- `POST /api/push`
- `GET /api/service/status`
- `POST /api/service/restart`

Runtime API:

- `GET /api/runtime/tool/{tool_id}`
- `POST /api/runtime/validate`
- `POST /api/runtime/dry-run`
- `POST /api/runtime/execute`
- `GET /api/audit`

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
pip install fastapi uvicorn
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
