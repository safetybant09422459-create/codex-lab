# Decision: Travel as Family Outing Memory

## 日付

2026-06

---

## テーマ

Travel Skillを、単なる旅行管理ではなく「家族のおでかけ記憶Skill」として扱う。

Skill名は現時点ではTravelのままとする。

---

## 背景

既存の旅行アプリは、宿泊旅行の管理だけでなく、家族で行きたい場所を候補として並べ、妻と相談し、当日まで未確定のSpotを残し、旅行後にメモと写真で思い出を見返す用途で使われている。

また、旅行だけでなく日帰りのおでかけも入っており、「去年何したっけ？」を振り返る用途にも使われている。

この実使用感は、Packing、Budget、Checklist中心の旅行管理よりも、Trip / Outing、Candidate Spot、Timeline、Cover Image、Photo Link、Memory中心の「家族のおでかけ記憶」に近い。

---

## 決定

Travel Skillは、家族旅行、日帰りのおでかけ、近場イベントを含むTrip / Outingを扱う。

Travelの核は以下とする。

* Trip / Outing
* Candidate Spot
* Experience
* Experience Type: spot, move, event, memo
* Timeline Item
* Memo
* Cover Image
* Photo Link
* Memory

Packing、Budget、Checklist、Souvenirは補助機能として扱う。

Experienceが本体である。spot / move / event / memoはExperienceのtypeであり、場所だけが思い出ではない。移動中も写真や思い出メモを持てる。

DB / 既存互換ではTimeline Itemと呼び、domain / API / MCP / ToolではExperienceと呼ぶ。

---

## Candidate Spot

計画時には、同じ時間帯に複数のSpot候補が存在できる。

例:

* 10:00 海遊館
* 10:00 レゴランド
* 10:00 通天閣

これは未確定計画として重要な状態である。

Spotは少なくとも以下の状態を持てるようにする。

* `candidate`
* `planned`
* `confirmed`
* `visited`
* `skipped`
* `cancelled`
* `unplanned`

候補はあとで採用、削除、時間変更、別時間帯への移動ができる。旅行当日まで候補のまま残ってもよい。

---

## Experience / Timeline Item

TimelineはExperienceを時系列で並べたViewであり、spotとmoveだけでは構成しない。

「お家出発！」のように、Google Placesにも写真にも紐づかないがTimeline上に置きたい出来事がある。

Experience Typeは以下を正式enumとする。

* `spot`
* `move`
* `event`
* `memo`

v0.1では既存`travel_timeline_items`をExperienceの保存実体として活かす。Timeline Itemは生成Viewではなく、DB / 既存互換上の保存Entity名である。

Timeline Viewは、保存済みExperienceを時刻や手動順序で並べた取得/表示結果である。

Spot / Move / Eventを別テーブル化しない。将来、移動経路、予約、Place正規化、検索性能などの理由が明確になった場合だけ派生テーブルを検討する。

---

## Experience CRUD

Canonical Tool:

* `travel.create_experience`
* `travel.get_experience`
* `travel.update_experience`
* `travel.archive_experience`

Alias / UI shortcut:

* `travel.add_spot`
* `travel.add_move`
* `travel.add_memo`

Aliasは本流ではない。UIや会話で入力を短くするための入口であり、内部では`experience_type`を指定したCanonical Toolへ寄せる。

既存互換:

* `travel.create_timeline_item`は既存互換として残す
* `travel.get_spot` / `travel.get_spot_photos`が存在する場合は既存互換として残し、将来`travel.get_experience` / `travel.get_experience_photos`へ寄せる

削除は物理削除ではなく`archived`状態または`archived_at`による論理アーカイブを基本にする。

---

## Cover Image

Cover ImageにはTrip代表画像とSpot代表画像がある。

Cover Imageの状態は以下を想定する。

* Google Places由来の仮画像
* Google Places Adapterによりローカル保存またはキャッシュ済みの画像
* 実際に撮影した家族写真へ置き換えた画像
* 置き換えずGoogle仮画像のまま残る画像

Google Places由来の仮画像はTravel + Google Places Adapter側で扱う。

家族が撮影した写真、Immich Asset、Album、ThumbnailはPhoto Skill側で扱う。

TravelはCover Imageとして採用された参照だけを保持する。

---

## Memory

旅行後の価値は、単なるReviewではなくMemoryである。

Memoryは以下をまとめる。

* 思い出メモ
* その時の写真
* 子どもの反応
* ここが良かった、また行きたいという記録
* もう一度見たい場面

将来は「去年の旅行ハイライト見せて」のような要求に対して、テレビや大画面に画像と思い出メモを流せるようにする。

写真の保存、検索、Thumbnail、Immich連携はPhoto Skillが担当する。TravelはどのTrip / Outing、Experience、Memoryに関連する写真かという文脈を担当する。

---

## Sharing / Access Control

将来、じいじばあばにもMemoryを見せたい。

ただし、家族全体の旅行や写真をすべて見せるのではなく、一緒に行ったTrip / Outingだけを見せたい。

Travel設計では以下を前提にする。

* Participantsは共有範囲の判断材料になる
* Trip、Memory、Memo、Photo Linkは可視性を持てるようにする
* 推定Photo Linkや子どもの写真を自動公開しない
* 共有範囲変更は確認と監査を必要とする更新系操作として扱う

本格的な権限管理は将来のFamily/ProfileまたはAccess Control系Skill候補と連携する。

---

## 影響

今回の判断は設計ドキュメントの補正であり、Runtime、Executor、API、DB、UIは変更しない。

将来の最小実装では、既存の`travels`、`spots`、`moves`を読み取り中心に活かしつつ、以下を段階的に追加する。

1. Experience statusによるCandidate Spot表現
2. Experience Type: spot, move, event, memo
3. Timeline View
4. Trip / Experience Cover Imageのsource/status
5. Memo
6. Memory
7. Photo Link
8. Participantsに基づく共有範囲

Packing、Budget、Checklistは必要になるまで補助機能として扱う。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。Trip / Outing、候補Spot、Timeline、MemoryはWeb UIで相談と振り返りに使える。
2. API / Toolとして利用できるか
   * 利用できる。Timeline取得、候補Spot更新、Memory作成をTool境界にできる。
3. 将来MCP Tool化できるか
   * できる。読み取り系のTrip、Timeline、Memoryから始められる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。UI状態ではなくTrip IDとEntity IDを中心に扱う。
5. UI依存のロジックになっていないか
   * なっていない。Cover ImageやTimelineは表示に使うが、Travelの状態と記憶文脈を表す。
6. 読み取り系か更新系か
   * 全体はmixed。初期はread中心、候補変更、Memory作成、共有変更はwrite。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。子どもの写真、位置情報、参加者、共有範囲、外部Place画像の扱いは確認と監査が必要。
