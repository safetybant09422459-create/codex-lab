# Runtime, Tools, Permissions, Confirmation and Audit

更新日: 2026-06-27

## 現在の構造

```text
FastAPI / Web UI / future Chat
  → RuntimeService
    → Tool Registry loader
    → required-field validation
    → PermissionEngine
    → ConfirmationEngine
    → ExecutorRegistry
      → WeatherExecutor / TravelExecutor / PhotoExecutor
      → StubExecutor（その他）
    → AuditLogger
```

Runtime API:

- `GET /api/runtime/tool/{tool_id}`
- `POST /api/runtime/validate`
- `POST /api/runtime/dry-run`
- `POST /api/runtime/execute`
- `GET /api/audit`

`RuntimeService.execute_stub` というmethod名は初期実装由来である。実際にはExecutor Registryに登録されたWeather / Travel / Photo Toolを実行する。method名だけを見て全Toolがstubだと判断しない。

## Skill Registry

`skills/*/skill.json` がSkill一覧の正。現在はweather、travel、photo、calendar、garden、home、developerがある。Skill JSONは説明、全体risk、例を持つ粗いmetadataで、個別Toolの実装状態を保証しない。

`GET /api/skills` はJSONを読みWeb UIへ返す。Travel / PhotoのSkill statusは現在 `idea` のままだが、配下の複数ToolとExecutorは実装済みである。

## Tool Registry

`tools/*/*.json` がTool contractの正。主なfield:

- `id`, `skill_id`, `name`, `description`, `status`
- `mode`: read / write / mixed
- `risk_level`: low / medium / high
- `confirmation_required`
- `audit_required`
- `input_schema`, `output_schema`

Runtimeは毎回Tool JSONを検索して定義をロードする。`GET /api/tools` は全定義またはSkill filterを返す。

重要な制約: 現行Validationが検査するのは `input_schema.required` の欠落だけである。type、enum、minimum、additional properties等はRuntime共通層では検証しておらず、一部はExecutor / Repositoryが検査する。Chat v0.1ではmodel出力を信用せず、server側でfull schema validationまたはTool別引数制約を追加する必要がある。

## Executor Registry

登録済み:

- weather → WeatherExecutor
- travel → TravelExecutor
- photo → PhotoExecutor

それ以外はStubExecutorへフォールバックする。Tool JSONに `status: implemented` があっても、実Executorの分岐がなければ実処理できるとは限らない。Chat allowlistはTool JSONだけで自動生成せず、実行可能性を明示的に管理する。

## Permission

現在のroleはadmin、family、guest。roleが不正または省略ならguest。

現行ルール:

- admin: 全Toolを許可
- family / guest: readかつlow riskだけ許可
- guest + developer: 明示拒否
- その他: 拒否

したがってTravelの一覧・詳細・timeline・Experience取得はfamily / guestで可能だが、medium-riskの写真readと全writeはadminが必要。これは簡易v0.1 Permissionであり、本格認証、resource ownership、family policy、field-level policyは未実装。

## Confirmation

Toolが `confirmation_required: true` またはhigh riskなら確認必須。現行APIはrequestの `confirmed` Booleanだけを見る。

Runtime内ではPermission判定が先、Confirmation判定が後。確認があっても権限不足は解消しない。

一般Chatでmodel自身に `confirmed: true` を設定させてはいけない。人間のUI操作から発行したshort-lived / single-use pending actionを、Tool、target、params、user/sessionへ束縛してRuntimeへ渡す。

## Audit

AuditLoggerは `logs/audit.log` にJSON Linesで追記し、`GET /api/audit` で最近のeventを返す。RuntimeはTool lookup失敗、validation失敗、permission denied、confirmation blocked、実行成功・失敗を記録する。eventにはrole、permission、risk、confirmation、audit_required、execution_mode等が含まれる。

現行コードはRuntime実行attemptを記録し、`audit_required` はevent属性として保持する。Chatでは会話全文や写真binary、secretをそのままAuditへ入れず、必要なID、hash、結果状態を中心にする。

## Chat v0.1のRuntime接続原則

- Browser → OpenAI直接接続は禁止
- Chat orchestrator → RuntimeServiceを必須経路にする
- server-side Tool allowlistを持つ
- readとwriteを別flowにする
- writeはpending action確認後だけ実行
- modelが生成したTool ID、role、confirmedを信用しない
- Tool resultをfield / size limitしてmodelへ渡す
- 同一Tool loop、最大Tool call数、timeoutを制限する
- Tool result内の文をsystem instructionとして扱わない
