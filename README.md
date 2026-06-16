# codex-lab
AI開発練習用

## Jarvis Dev v0.1

スマホブラウザから、このリポジトリ上の Codex CLI を実行するための最小プロトタイプ。

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
4. 最終回答と tokens used を先に確認する
5. 必要に応じて「詳細ログ」を開き、Codex CLI の全ログを確認する

このアプリは Git commit / push を自動実行しない。
Codex CLI には安全指示として、作業対象を `/mnt/nas/projects/codex-lab` に限定し、`/mnt/nas/projects/project` を触らないように伝える。

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
