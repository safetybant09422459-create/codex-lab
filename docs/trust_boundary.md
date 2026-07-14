# Jarvis Trust Boundary

## Current local-development boundary

Jarvis Dev v0.3は、Raspberry Pi上のローカル開発環境で開発者本人が利用するプロトタイプである。
日々の開発効率を優先する期間として、Developer APIはDeveloper UIと同一originから認証なしで利用できる。
`JARVIS_ENABLE_DEVELOPER_API`、`JARVIS_DEVELOPER_TOKEN`、Bearer tokenには依存しない。

これは「セキュリティ不要」という判断ではない。Developer endpointにはCodex実行、repository内容の表示、
git操作、service操作など強い権限があるため、インターネットへ公開せず、信頼できるローカルネットワークと
端末からだけ利用する。port forwarding、公開reverse proxy、第三者が接続できるネットワークでは運用しない。

RuntimeのValidation、Permission、Confirmation、Audit、Developer UIでの明示確認、git preflightは引き続き有効である。
これらはネットワーク認証の代替ではなく、各操作の安全境界として維持する。

## Codex subprocess and log

Codex subprocessへ渡す環境変数は`PATH`、`HOME`、`LANG`、`LC_ALL`、`LC_CTYPE`、`TERM`、`TMPDIR`、
`XDG_CONFIG_HOME`、`CODEX_HOME`のallowlistに限定する。`HOME` / `XDG_CONFIG_HOME` / `CODEX_HOME`はCodex CLIの
設定とsession resumeに必要であり、OpenAI、Immichその他のJarvis secretは継承しない。

Codex raw logと抽出したfinal answerはAPI responseを作る前に既存secret patternでredactする。一般的なprovider token、
credential assignment、private key、Authorization headerを`[REDACTED]`へ置換する。保存済みのprocess-local log自体を
secret storeとして扱ってはならず、secretをpromptや出力へ含めないことが前提である。

## Future reintroduction boundary

インターネット公開、複数ユーザー対応、信頼できないネットワークからの接続を行う前に、Developer認証を現方式の
復元ではなく再設計する。Consumer Plane / Developer Planeの別process・port・Unix userへの分離、TLS / trusted proxy、
server-owned principal、権限モデル、Confirmation Transaction、永続監査、secret store、session失効を合わせて検討する。

## Private response policy

全`/api/` responseへ`Cache-Control: no-store`を付ける。将来cache可能な公開Catalogが必要なら個別に再検討する。
全responseへ`X-Content-Type-Options: nosniff`と`Referrer-Policy: no-referrer`を付ける。これは認証、Permission、
visibility、process分離の代替ではない。

Web responseにはself-onlyを基本とするContent Security Policyを付け、script、style、image、font、connect先を
同一originへ制限する（imageは`data:`も許可）。`object-src`、`base-uri`、`frame-ancestors`を無効化する。将来Voice、
Camera、外部ProviderへのBrowser直接接続が必要でも一括緩和せず、Capabilityとprivacy review後に必要なdirectiveだけを
追加する。
