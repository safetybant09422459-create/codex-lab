# Jarvis Screen

## 目的

Jarvis Screenは、Jarvis Shellのトップ画面である。

これは単なるメニューや固定ダッシュボードではない。

Jarvis CoreがTravel、Photo、Garden、Calendar、Home、Developerなどの情報を統合し、その時に見せるべき情報を表示する場所である。

関連する前提は以下を参照する。

* [Architecture](architecture.md)
* [Glossary](glossary.md)
* [Principles](principles.md)
* [Skill Standard Architecture](skill_standard_architecture.md)
* [Roadmap](roadmap.md)

---

## 現時点の位置づけ

Jarvis Screenは、現時点では「喋らないJarvis」である。

双方向会話、音声入力、通知、自律提案へ進む前段階として、Jarvisが今見せるべき情報を画面に出すための場所とする。

初期実装では、表示内容はプレースホルダーや静的な候補でもよい。

ただし設計上は、固定メニューや常時表示ダッシュボードではなく、将来Jarvis CoreやSkill Routerが文脈に応じて表示内容を選べる場所として扱う。

---

## 表示候補

Jarvis Screenに表示される候補:

* 今日の予定
* 天気
* 次の旅行
* 最近の写真
* Gardenの水やり
* Homeの注意
* Developerの状態
* Jarvisからの提案

表示候補は常に全部出すものではない。

Jarvis Core、Memory、Skill、Tool結果、ユーザー文脈に基づき、その時に必要なものを選んで表示する。

---

## 表示シナリオ

### 朝

表示候補:

* 今日の予定
* 天気
* 出発前の注意

朝は、行動開始に必要な情報を優先する。

### 旅行前

表示候補:

* 旅行まであと何日
* 持ち物
* 現地の天気
* 未確認の予約や予定

旅行前は、Travel SkillとCalendar Skillの情報を統合して、準備に関係する情報を優先する。

### 帰宅後

表示候補:

* 今日の写真
* 旅行や外出の振り返り
* 保存すべき思い出の候補

帰宅後は、Photo SkillやTravel Skillの結果をもとに、記録や振り返りにつながる表示を優先する。

### 雨の日

表示候補:

* 傘の注意
* 外出予定
* 洗濯注意
* GardenやHomeへの影響

雨の日は、天気、Calendar、Garden、Homeの情報を合わせて、生活上の注意を表示する。

### 開発中

表示候補:

* Developerの未push変更
* Codex実行状態
* 失敗中のチェック
* 次に確認すべき開発タスク

開発中は、Developer SkillまたはDeveloper Tool候補から受け取った状態を表示する。

---

## Jarvis Core / Skillとの関係

Jarvis Screenは、各Skillの詳細画面ではない。

Travel、Photo、Garden、Calendar、Home、Developerの詳細操作は、それぞれのSkill画面やTool境界で扱う。

Jarvis Screenは、それらの結果から今見るべき要約、提案、確認入口を表示する。

```text
Travel / Photo / Garden / Calendar / Home / Developer
↓
Skill Tool / Repository / Adapter
↓
Runtime
↓
Jarvis Core / Skill Router
↓
Jarvis Screen
```

Jarvis Screenは表示先であり、Tool実行主体ではない。

---

## 非責務

Jarvis Screenが担当しないこと:

* 各Skillの詳細画面そのものではない
* すべての情報を常に表示する固定ダッシュボードではない
* AIの実行権限を持たない
* Toolを直接実行しない
* Skill固有のDB操作を持たない
* Home SkillをJarvis本人として扱わない

Jarvis ScreenがToolを直接実行すると、権限、確認、監査、API / MCP化の境界が曖昧になる。

実行が必要な場合は、Jarvis Core、Runtime、Skill Routerなどの境界へ委譲する。

---

## 将来像

Jarvis Screenは、以下と接続して、映画のJarvis的な双方向性へ進化する土台である。

* Chat入力
* Voice入力
* Notification
* Planner
* Memory
* Skill Router

将来的には、Jarvis Screenは単なる表示画面ではなく、提案、確認、説明、対話の入口になる。

ただし、実行権限や判断の本体をScreenへ集めない。

Screenは、Jarvis Coreが判断した内容、Runtimeが安全境界を通した結果、Skillが返した要約を、人間が見て理解できる形で表示する。

---

## 設計上の注意

### 固定ダッシュボードにしない

全部の情報を並べる画面にすると、Jarvis Coreが「今必要なものを選ぶ」余地がなくなる。

Jarvis Screenは、情報量より文脈適合を優先する。

### Skill詳細を混ぜない

Travelの旅程編集、Photoのアルバム管理、Homeの家電操作などは各Skill画面で扱う。

Jarvis Screenは要約、提案、注意、入口を表示する。

### 更新操作は確認を通す

Jarvis Screenから更新系操作へ進む場合は、RuntimeのPermission / Confirmation / Auditを経由する。

特にHome、Photo、Calendar、Travel writeは、家族の安全、プライバシー、予定、生活に影響するため注意する。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。Jarvis ScreenはJarvis Shellのトップ画面である。
2. API / Toolとして利用できるか
   * ScreenそのものはToolではない。表示内容の取得や提案生成はAPI / Tool境界へ分離できる。
3. 将来MCP Tool化できるか
   * Screen自体ではなく、表示候補を作るSkill操作や要約取得はMCP Tool候補にできる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。Coreが選んだ表示結果をScreenが受け取って表示する構造にする。
5. UI依存のロジックになっていないか
   * してはいけない。Screenは表示先であり、判断と実行はCore / Runtime / Skill側に置く。
6. 読み取り系か更新系か
   * 基本は読み取り系の表示である。更新へ進む場合は確認付き操作として扱う。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。予定、写真、家の状態、開発状態、位置情報を扱う可能性があるため、表示範囲と更新権限を分ける。
