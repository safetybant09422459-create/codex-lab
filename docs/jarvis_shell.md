# Jarvis Shell

## 目的

Jarvis Shellは、Jarvisアプリ全体の骨組みである。

ユーザー向け名称ではなく、開発上の呼び名として扱う。

Jarvis Shellは、Jarvis Core、Runtime、Skill群、Developer UIをWeb UI上で受け止めるための共通入口である。個別Skillの中身を実装する場所ではなく、各Skill画面や将来のCore判断結果を表示するための器である。

関連する前提は以下を参照する。

* [Architecture](architecture.md)
* [Glossary](glossary.md)
* [Principles](principles.md)
* [Skill Standard Architecture](skill_standard_architecture.md)
* [Roadmap](roadmap.md)

---

## 役割

Jarvis Shellが担当すること:

* 共通レイアウト
* 画面切替
* ナビゲーション
* 各Skill画面の受け皿
* Developer UIへの導線
* 将来Jarvis Core / Runtime / Skill Routerからの表示結果を受け取る入口

Jarvis Shellは「どの画面を見せるか」「どのSkill画面へ移動するか」「共通UIとしてどの入口を提供するか」を扱う。

ただし、Skillのドメイン判断、Tool実行、DB操作、AI判断はShellの責務ではない。

---

## 初期ナビゲーション

Jarvis Shell v0.1の初期ナビゲーションは以下とする。

```text
Jarvis
├ Travel
├ Photo
├ Garden
├ Calendar
├ Home
└ Developer
```

`Jarvis` はトップ入口であり、`Home` とは呼ばない。

`Home` はHome Control / Home Automation Skillであり、家電、家の状態、消し忘れ、在宅、旅行モードなどを扱うSkill候補である。

---

## 各画面の初期状態

| 画面 | 初期状態 |
| --- | --- |
| Jarvis | 将来のJarvis Screen。最初はプレースホルダーでよい |
| Travel | 将来Travel Skillを表示する |
| Photo | 将来Photo Skillを表示する |
| Garden | 将来Garden Skillを表示する |
| Calendar | 将来Calendar Skillを表示する |
| Home | Home Control / Home Automation Skillを表示する。Jarvis本人ではない |
| Developer | 管理者向けDeveloper UIへの導線を表示する |

初期実装では、各Skill画面はプレースホルダーでもよい。

重要なのは、Shellが将来のSkill実装を差し込める構造を持ち、各Skillの内部ロジックをShellへ持ち込まないことである。

---

## Jarvis Core / Runtimeとの関係

Jarvis ShellはUIの入口である。

Jarvis Coreは、Skill、Tool、Runtime、Memory、AI Agentをつなぐ中核である。

Runtimeは、Toolを安全に実行するための実行境界である。

```text
Jarvis Shell
↓
Jarvis Core / API / Skill Router
↓
Runtime
↓
Permission / Confirmation / Audit
↓
ExecutorRegistry
↓
SkillExecutor
↓
SkillRepository
↓
Storage または External Adapter
```

Shellは、CoreやSkill Routerから受け取った表示結果、操作入口、確認要求を表示する。

Tool実行が必要な場合も、Shellが直接実行するのではなく、API、Core、Runtimeなどの境界を経由する。

---

## 非責務

Jarvis Shellが担当しないこと:

* Travelのドメインロジックを持たない
* Photoのドメインロジックを持たない
* Runtimeの実行ロジックを持たない
* Skill固有のDB操作を持たない
* AI判断ロジックを直接持たない
* Toolを直接実行しない
* HomeをJarvis本人やトップ画面の別名として扱わない

ShellにSkill固有ロジックを入れると、Web UI以外のChat、Voice、MCP、Future Robotから同じ機能を呼び出しにくくなる。

---

## 設計原則

### UIは入口

UIはSkillやJarvis Coreを利用するための入口である。

重要な判断やドメインロジックはUIに閉じ込めない。

### Tool First

各機能はToolとして設計する。

Shell上のボタンや画面遷移は、将来API / Tool / MCP Tool候補からも呼べる構造を壊さない。

### Skill独立

Travel、Photo、Garden、Calendar、Home、Developerは独立したSkillまたはTool候補として扱う。

Shellはそれらを並べるが、内部実装には依存しない。

### Runtime経由

実行、権限、確認、監査が必要な処理はRuntime境界を経由する。

Shellは確認画面や結果表示を担当できるが、実行可否の判断や監査の実体はRuntime側に置く。

### 将来の入口を壊さない

Jarvis ShellはWeb UI用の骨組みだが、Jarvis全体はWeb UIだけで完結しない。

将来MCP、Chat、Voiceから同じSkillを呼べるように、Shell固有の状態や条件分岐へ重要な処理を閉じ込めない。

### Safari First

Jarvis ShellはSafari Firstで実装する。

iPhone / Safari は主要利用端末に含まれるため、Chromeで動いてもSafariで壊れる状態は未完成として扱う。

Shellが壊れてもDeveloper UIを巻き込まない構造を優先する。

Shell / Runtime Execute / Developer UI の初期化はできるだけ分離し、一部のfrontend JSの失敗が全体停止にならないようにする。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。Jarvis Shell自体がWeb UIの共通入口である。
2. API / Toolとして利用できるか
   * ShellそのものはToolではない。Shell上の操作はAPI / Tool境界へ接続できる構造にする。
3. 将来MCP Tool化できるか
   * ShellはMCP Tool化対象ではないが、Shellが扱う各Skill操作はMCP Tool候補にできる。
4. Jarvis Coreから呼び出せるか
   * Coreが返す表示結果や確認要求をShellが表示する構造にできる。
5. UI依存のロジックになっていないか
   * してはいけない。Shellは表示、ナビゲーション、操作入口に限定する。
6. 読み取り系か更新系か
   * Shell自体は表示と入口であり、読み取り / 更新の実行主体ではない。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。Shellから更新系Toolへ進む場合は、RuntimeのPermission / Confirmation / Auditを必ず経由する。
