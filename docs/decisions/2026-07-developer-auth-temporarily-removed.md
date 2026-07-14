# Developer Authentication Temporarily Removed

日付: 2026-07-14

## Status

Accepted

## Decision

Jarvis Dev v0.3のDeveloper API認証を一旦撤去する。Developer UIとDeveloper APIは、Raspberry Pi上の
ローカル開発環境で開発者本人が利用する間、追加認証なしで同一originから利用可能にする。

`JARVIS_ENABLE_DEVELOPER_API`、`JARVIS_DEVELOPER_TOKEN`、Bearer token、token入力UI、token生成用
EnvironmentFileには依存しない。

## Reason

現在は開発段階であり、インターネット公開や複数ユーザー利用を行っていない。現時点ではDeveloper認証による
保護より、毎日のtoken入力、設定、移行運用による開発効率低下の方が大きい。

## Boundaries retained

* Developer APIはインターネットへ公開せず、信頼できるローカルネットワークと端末からだけ利用する。
* RuntimeのValidation、Permission、Confirmation、Auditは維持する。
* Codex subprocessの環境変数allowlist、secret redaction、git preflight、UIの副作用確認は維持する。
* Developer endpointがConsumer Planeと同じprocess、port、Unix userを共有するリスクは既知として扱う。

## Reconsideration conditions

次のいずれかを行う前に再設計する。

* インターネット公開またはport forwarding
* 複数ユーザー、家族ユーザー、第三者による利用
* 信頼できないLANや端末からの接続
* Developer操作をJarvis Core、Chat、Voice、MCPから呼び出すこと

再導入時は単一Bearer tokenの復元だけで済ませず、Consumer / Developer Planeのprocess・port・Unix user分離、
TLS / trusted proxy、server-owned principal、操作単位の権限、Confirmation Transaction、永続監査、secret store、
session失効を一体として検討する。
