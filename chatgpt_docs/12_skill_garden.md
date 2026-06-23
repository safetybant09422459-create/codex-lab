# Garden Skill

## 目的

Garden Skillは、家庭菜園や植物管理を扱うSkillである。

現在のdocsでは詳細設計は少ないが、Idea BacklogとTool定義から、初期は水やりやタスク管理を中心に扱う。

将来は成長記録、病害虫診断、開花予測、AI栽培アドバイスへ拡張する。

## 扱う対象

Gardenが扱う対象:

* 水やりタスク
* 植物ごとの作業
* 成長記録
* 病害虫メモ
* 開花・収穫予測
* 天気との関係
* 家族への通知候補

## 現在のTool定義

Skill:

* `id: garden`
* `mode: mixed`
* `risk_level: medium`
* `confirmation_required: false`
* `audit_required: true`

Tools:

* `get_tasks`
  * `mode: read`
  * `risk_level: low`
* `add_task`
  * `mode: write`
  * `risk_level: medium`

## 責務

Gardenの責務:

* Gardenタスクを一覧表示する
* 水やり、追肥、剪定などの作業を登録する
* 作業の期限、状態、対象植物を管理する
* 将来、天気や季節情報を使って作業提案を行う
* 将来、写真やメモを成長記録として扱う

## 非責務

Gardenが扱わないもの:

* 家全体の家電制御
* Calendar全体の予定管理
* Photo全体の写真管理
* Weather APIの実装詳細
* 通知基盤そのもの

天気、写真、通知、予定が必要な場合は、各Skill / Toolの抽象を経由する。

## 将来のTool候補

読み取り:

* `garden.get_tasks`
* `garden.get_plants`
* `garden.get_plant_status`
* `garden.get_today_care`
* `garden.suggest_watering`

更新:

* `garden.add_task`
* `garden.complete_task`
* `garden.add_plant`
* `garden.record_growth`
* `garden.record_pest_issue`
* `garden.update_care_schedule`

## 他Skillとの関係

### Weather

雨、気温、乾燥、台風などはGarden提案に影響する。

GardenはWeather API詳細を持たず、Weather Toolから必要な天気情報を取得する。

### Photo

成長記録や病害虫診断では写真が必要になる。

写真AssetやThumbnailはPhoto Skillが扱う。Gardenは採用したPhoto参照や記録文脈を持つ。

### Calendar

定期作業や通知はCalendarと接続できる。

Calendar予定そのものの管理はCalendar Skillに置く。

### Jarvis Screen

Jarvis Screenには「今日の水やり」「雨なので水やり不要」「病害虫確認」などを要約表示できる。

## Risk / Permission

Gardenは家庭内の植物管理であり、一般にはTravelやPhotoより低リスクだが、作業通知、家族への依頼、写真、外部診断APIを使う場合は注意する。

分類目安:

* タスク一覧: read / low
* タスク追加、完了: write / medium
* 写真付き診断: read or mixed / medium
* 外部AI診断へ写真送信: high候補

## 設計メモ

Gardenは、初期はタスク管理に留める。

ただし将来のAI栽培アドバイスを見据え、UIに作業判断ロジックを閉じ込めない。植物、作業、履歴、写真、天気をRepository側で扱えるようにする。

## Jarvis Principle Check

1. Web UIから利用できるか: Garden画面やJarvis Screenで利用できる。
2. API / Toolとして利用できるか: `get_tasks`、`add_task`として利用できる。
3. 将来MCP Tool化できるか: Garden Task / Plant Toolとして可能。
4. Jarvis Coreから呼び出せるか: Runtime経由で呼び出せる。
5. UI依存のロジックになっていないか: タスク判断や提案はRepository / Tool側へ置くべき。
6. 読み取り系か更新系か: mixed。`get_tasks`はread、`add_task`はwrite。
7. 副作用・権限・プライバシー上の注意はあるか: 家族への通知、写真、外部診断API送信は確認と権限が必要。
