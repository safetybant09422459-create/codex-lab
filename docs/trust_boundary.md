# Jarvis Trust Boundary v0.1

## Stage 0: Developer API containment

Stage 0は、Consumer PlaneとDeveloper Planeが同じFastAPI process、port、Unix userを共有する現状で、
Developer制御機能をfail-closedにする緊急封じ込めである。これはprocess分離の代替ではない。

Developer endpointは共通`APIRouter` dependencyで保護し、次の両方を満たす場合だけhandlerへ進む。

* `JARVIS_ENABLE_DEVELOPER_API=true`（`1`、`yes`、`on`も許可）
* `Authorization: Bearer <JARVIS_DEVELOPER_TOKEN>`がserver-side tokenと一致する

tokenはquery parameter、request bodyでは受け付けない。無効時は`404`、有効だがtoken設定がない場合は`503`、
認証不一致は`401`を返す。tokenをresponse、Audit、application log、frontend bundleへ記録・埋め込みしてはならない。
Developer UI自身はtokenを保持しないため、利用する場合は同一originの信頼できる認証proxy等がAuthorization headerを
付与するか、API clientからheaderを指定する。平文HTTPでtokenを送信しない。

```bash
JARVIS_ENABLE_DEVELOPER_API=true \
JARVIS_DEVELOPER_TOKEN='<secret-storeから供給>' \
uvicorn backend.main:app --host 127.0.0.1 --port 8001

curl -H "Authorization: Bearer $JARVIS_DEVELOPER_TOKEN" \
  http://127.0.0.1:8001/api/project
```

保護対象はCodex実行・session、project状態、Runtime Audit、Codex logs、git changes / diff / preflight / commit-push、
service status / restartである。Chat、Travel、Photo、Provider / Runtimeの既存consumer経路にはDeveloper tokenを
要求しない。Runtime request bodyの`role`と`confirmed`を全面廃止する作業は本段階に含めない。

## Codex subprocessとlog

Codex subprocessへ渡す環境変数は`PATH`、`HOME`、`LANG`、`LC_ALL`、`LC_CTYPE`、`TERM`、`TMPDIR`、
`XDG_CONFIG_HOME`、`CODEX_HOME`のallowlistに限定する。`HOME` / `XDG_CONFIG_HOME` / `CODEX_HOME`はCodex CLIの
設定とsession resumeに必要であり、OpenAI、Immich、Developer tokenその他のJarvis secretは継承しない。

Codex raw logと抽出したfinal answerはAPI responseを作る前に既存secret patternでredactする。一般的なprovider token、
credential assignment、private key、Authorization headerに加え、設定中のDeveloper token実値を`[REDACTED]`へ置換する。
保存済みのprocess-local log自体をsecret storeとして扱ってはならず、secretをpromptや出力へ含めないことが前提である。

## Remaining boundary

同一processである以上、Developer codeとConsumer codeは同じmemory、filesystem permission、service identity、障害範囲を
共有する。次段階ではDeveloper Routerを別FastAPI appへ移し、Consumer Plane / Developer Planeを別process、別port、
別Unix userへ分離する。network exposure、TLS / trusted proxy、secret store、server-owned principal、Confirmation
Transaction、監査保存先もその段階で再設計する。
