# Calendar Skill

## 目的

Calendar Skillは、家族の予定を扱うSkillである。

今日の予定、朝の予定要約、出発時間通知、家族スケジュール統合、プライバシーレベルを扱い、Jarvisが日常行動を支援できる状態にする。

## 扱う対象

Calendarが扱う対象:

* Event
* 今日の予定
* 家族ごとの予定
* 出発時間
* 移動時間
* 通知候補
* プライバシーレベル
* 習慣分析

## 現在のTool定義

Skill:

* `id: calendar`
* `mode: mixed`
* `risk_level: medium`
* `confirmation_required: true`
* `audit_required: true`

Tool:

* `get_events`
  * `mode: read`
  * `risk_level: medium`

## 責務

Calendarの責務:

* 指定範囲の予定を取得する
* 今日の予定を要約する
* 家族ごとの予定表示と権限制御を行う
* 出発時間や準備に関わる情報をJarvis Screenへ渡す
* 将来、予定作成・変更・削除をToolとして扱う
* TravelやHomeと連携し、旅行前や外出前の注意を出す

## 非責務

Calendarが扱わないもの:

* TravelのTrip / Experienceの正
* Home家電制御
* Weather APIの実装詳細
* Photo管理
* 通知送信基盤そのもの

Calendarは予定の文脈を持つ。旅行の計画詳細はTravel、家電や在宅はHome、天気はWeatherが扱う。

## 将来のTool候補

読み取り:

* `calendar.get_events`
* `calendar.get_today_events`
* `calendar.summarize_today`
* `calendar.get_family_schedule`
* `calendar.estimate_departure_time`

更新:

* `calendar.create_event`
* `calendar.update_event`
* `calendar.cancel_event`
* `calendar.set_event_privacy`
* `calendar.create_reminder`

## Privacy

Calendarは家族の予定を扱うため、Privacy Firstの中心領域である。

可視性候補:

* `private`: 本人だけ
* `busy`: 時間帯だけ表示
* `family`: 家族に詳細表示
* `shared`: 外部共有可能

子どもの予定、病院、学校、仕事、個人予定は不用意に共有しない。

## 他Skillとの関係

### Travel

旅行前にはCalendarとTravelを組み合わせる。

例:

* 旅行まであと何日
* 出発予定時刻
* 未確認の予約や予定
* 現地天気

Tripそのものの正はTravelに置く。

### Weather

雨、気温、台風などは予定や出発時間に影響する。

CalendarはWeather API詳細を持たず、Weather Toolから必要な情報を受け取る。

### Home

外出や旅行予定に応じて、Homeが旅行モードや消し忘れ注意を出せる。

家電制御はHome Skill側で扱う。

### Jarvis Screen

朝のJarvis Screenでは、今日の予定、天気、出発前の注意を組み合わせて表示できる。

## Risk / Permission

予定の読み取りでも家族プライバシーに関わるため、`risk_level: medium`が妥当である。

更新系は確認と監査を必要とする。

分類目安:

* 予定一覧: read / medium
* 予定作成・変更・削除: write / medium
* 外部共有、通知送信: high候補

## Jarvis Principle Check

1. Web UIから利用できるか: Calendar画面やJarvis Screenで利用できる。
2. API / Toolとして利用できるか: `get_events`および将来の予定CRUD Toolで利用できる。
3. 将来MCP Tool化できるか: 予定取得、要約、作成をMCP候補にできる。
4. Jarvis Coreから呼び出せるか: Runtime経由で呼び出せる。
5. UI依存のロジックになっていないか: 予定解釈と権限判断はCore / Repository側へ置くべき。
6. 読み取り系か更新系か: mixed。現状Toolはread、将来CRUDはwrite。
7. 副作用・権限・プライバシー上の注意はあるか: 家族予定、子ども予定、仕事、病院、共有通知は慎重に扱う。
