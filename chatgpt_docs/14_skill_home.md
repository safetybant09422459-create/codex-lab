# Home Skill

## 目的

Home Skillは、Home Control / Home Automation系Skillである。

Jarvis本人やトップ画面ではない。`Home` は家電、家の状態、消し忘れ、在宅、旅行モードなど、家庭内の物理状態や現実世界への作用を扱う能力領域である。

## 命名

`Jarvis`:

* 家庭用AIエージェント全体
* UI上のトップ入口
* 複数Skillを統合して今見るべき情報を表示する画面

`Home Skill`:

* Home Control / Home Automation系Skill
* 家電や家の状態を扱う
* 他Skillと同列の能力領域

HomeをJarvis本人やトップ画面の別名として扱わない。

## 扱う対象

Homeが扱う対象:

* 家電
* 家の状態
* 消し忘れ
* 在宅
* 旅行モード
* 防犯モード
* おやすみモード
* エアコン提案
* 家族の生活パターンに関係するセンサー情報

## 現在のTool定義

Skill:

* `id: home`
* `mode: mixed`
* `risk_level: high`
* `confirmation_required: true`
* `audit_required: true`

Tool:

* `get_home_status`
  * `mode: read`
  * `risk_level: medium`

## 責務

Homeの責務:

* 家の状態を取得する
* 家電状態を取得する
* 消し忘れや異常を検知する
* 旅行モードや在宅状態を扱う
* 将来、家電操作をToolとして提供する
* CalendarやTravelと連携し、外出前や旅行中の注意を出す

## 非責務

Homeが扱わないもの:

* Jarvisトップ画面そのもの
* Jarvis Coreの人格やAI判断本体
* Calendar予定の正
* TravelのTrip / Experienceの正
* Photo管理
* Weather APIの実装詳細

## 将来のTool候補

読み取り:

* `home.get_home_status`
* `home.get_device_status`
* `home.get_energy_status`
* `home.get_security_status`
* `home.check_left_on_devices`

更新:

* `home.turn_off_light`
* `home.set_aircon`
* `home.set_travel_mode`
* `home.set_security_mode`
* `home.turn_off_all`

## Risk / Permission

Homeは高リスクSkill候補である。

理由:

* 現実世界へ作用する
* 家族の在宅情報を扱う
* 生活パターンを扱う
* 防犯や安全に影響する
* 誤操作が家族の生活に直接影響する

分類目安:

* 状態取得: read / medium
* 家電操作: write / high
* 防犯モード変更: write / high
* 在宅情報表示: read / medium to high

更新系は、Permission / Confirmation / Auditを必ず通す。

## 他Skillとの関係

### Calendar

外出予定や帰宅予定に応じてHomeが注意を出す。

例:

* 出発前に電気の消し忘れを確認
* 帰宅前にエアコン提案

予定の正はCalendarに置く。

### Travel

旅行中や出発前にHomeが旅行モードを扱える。

例:

* 旅行モードに切り替える
* 不在中の家の状態を確認する

Tripの正はTravelに置く。

### Weather

気温や雨によってHome提案が変わる。

例:

* 高温時のエアコン提案
* 雨の日の窓閉め注意

Weather API詳細はWeather側に置く。

### Jarvis Screen

Jarvis ScreenにはHomeの注意を要約表示できる。

例:

* 電気がついたまま
* 旅行モード中
* 雨なので窓注意

Jarvis Screenは表示先であり、Home操作を直接実行しない。

## 設計注意

Homeは最初から完全自動化しない。

基本は:

```text
Jarvisが提案
↓
人間が確認
↓
Runtimeが権限・確認・監査
↓
Home Toolが実行
```

生活に影響する操作は、UIのボタンだけで直接実行せず、Runtime境界を通す。

## Jarvis Principle Check

1. Web UIから利用できるか: Home画面やJarvis Screenで状態表示と確認付き操作に使える。
2. API / Toolとして利用できるか: `get_home_status`および将来の家電操作Toolとして利用できる。
3. 将来MCP Tool化できるか: 状態取得から始め、操作系は強い確認付きで候補にできる。
4. Jarvis Coreから呼び出せるか: Runtime経由で呼び出せる。
5. UI依存のロジックになっていないか: 操作判断と権限確認はUIではなくCore / Runtime / Home Repositoryへ置く。
6. 読み取り系か更新系か: mixed。状態取得はread、家電操作はwrite。
7. 副作用・権限・プライバシー上の注意はあるか: 現実世界への作用、在宅情報、生活パターン、防犯に強い注意が必要。
