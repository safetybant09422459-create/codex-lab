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
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

スマホのブラウザで以下を開く。

```text
http://<ラズパイのIPアドレス>:8000
```

### 使い方

基本の流れは 開発 → レビュー → 更新。

1. 画面上部で Project 名、Local Path、Branch、Git 状態を確認する
2. ChatGPT 等で作った設計書を「開発」タブへ貼り付ける
3. Jarvis Dev が生成した Codex 送信用プロンプトを確認・編集する
4. 「Codexへ送信」を押し、確認ダイアログで承認してから Codex を実行する
5. 「レビュー」タブで最終回答、tokens used、`git status`、変更ファイル、差分を確認する
6. 必要な場合だけ「レビュー」タブの Commit / Push を人間が明示操作する
7. 「更新」タブで `jarvis-dev` の systemd 状態を確認し、必要な場合だけ確認後に再起動する
8. Codex の生ログは「詳細ログ」タブで確認する

このアプリは Git commit / push を自動実行しない。
Codex CLI には安全指示として、作業対象を `/mnt/nas/projects/codex-lab` に限定し、`/mnt/nas/projects/project` を触らないように伝える。
Codex CLI には `git commit` と `git push` を実行しないように伝える。

### タブ

- 「開発」: 設計書貼り付け欄から Codex 送信用プロンプトを生成し、送信前に編集・承認
- 「レビュー」: 最終回答、tokens used、git status、変更ファイル、diff、Commit、Push
- 「更新」: `systemctl status jarvis-dev` と確認付き `systemctl restart jarvis-dev`
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
- `POST /api/run`
- `GET /api/logs`
- `GET /api/changes`
- `GET /api/diff?path=<path>`
- `POST /api/commit`
- `POST /api/push`
- `GET /api/service/status`
- `POST /api/service/restart`

### 設定

Codex CLI が `codex` 以外のパスにある場合は `CODEX_BIN` を指定する。

```bash
CODEX_BIN=/path/to/codex uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Codex CLI の引数を変えたい場合は `CODEX_ARGS` を指定する。
デフォルトは `exec`。

```bash
CODEX_ARGS="exec" uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
