# codex-lab
AI開発練習用

## Jarvis Dev v0.2

スマホブラウザから、このリポジトリ上の Codex CLI を実行し、変更内容を人間が確認してから Git に反映するためのプロトタイプ。

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

1. 入力欄に Codex へ渡すプロンプトを書く
2. 「実行」を押す
3. 画面上部の状態（実行中 / 完了 / 失敗）を確認する
4. 「最終回答」タブで最終回答と tokens used を確認する
5. 「変更ファイル」タブで最新の `git status --short` と変更ファイル一覧を確認する
6. 「差分」タブでファイルごとの差分を確認する
7. 「Git操作」タブで、必要な場合だけ Commit または Push を実行する

このアプリは Git commit / push を自動実行しない。
Codex CLI には安全指示として、作業対象を `/mnt/nas/projects/codex-lab` に限定し、`/mnt/nas/projects/project` を触らないように伝える。
Codex CLI には `git commit` と `git push` を実行しないように伝える。

### 変更確認

「変更ファイル」タブでは以下を確認できる。

- 新規ファイル
- 変更ファイル
- 削除ファイル
- `git status --short` の出力

「差分」タブでは、ファイルごとの差分を折りたたみ表示で確認できる。

### Git操作

Git 操作は Jarvis Dev 側の API だけが実行する。

- 「却下」: Git 操作は実行せず、画面上で却下したことを記録する
- 「Commit」: コミットメッセージ入力欄の内容で `git add -A` と `git commit -m` を実行する
- 「Push」: 確認ダイアログ後、さらに `PUSH` と入力した場合だけ `git push` を実行する

Commit のデフォルトメッセージは `Update Jarvis Dev v0.2`。
ユーザーは画面上で編集できる。

### API

- `POST /api/run`
- `GET /api/logs`
- `GET /api/changes`
- `GET /api/diff?path=<path>`
- `POST /api/reject`
- `POST /api/commit`
- `POST /api/push`

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
