# Travel UI Experience Principle

## 目的

この文書は、Travel Web UIで失ってはいけない体験原則を定義する。

現行TravelアプリのUIは、星野リゾートやホテルの「過ごし方」ページを参考にしている。重要なのは見た目の装飾だけではなく、見やすさ、旅行前のワクワク感、家族写真と思い出の結びつきである。

この原則はWeb UI / 画面表示向けである。MCP Tool、Chat、APIでは同じ見た目を強制しない。ただし、Web UIがこの体験を再現できるだけの構造化データは返せる必要がある。

---

## 参考思想

Travelは、旅行前には家族のおでかけ計画としてワクワクでき、旅行後には思い出を振り返れる画面であるべきである。

UIで大切にするもの:

* 一目で分かる見やすさ
* 旅行前のワクワク感
* Timeline Itemと家族の思い出の結びつき
* 画像を見るだけで「いつ・誰が・何をした」が分かること
* 子どもの写真を見たとき、何歳くらいの時かを直感的に思い出せること

参考にするのは、星野リゾートやホテルの「過ごし方」ページにある、大きな画像、分かりやすいタイトル、体験を順に見せる構成である。Timelineはデータ行ではなく、家族にとって意味のある体験の連なりとして見える必要がある。

---

## Timeline Experience Card

TravelのTimelineカードはExperience Cardとして扱う。

現行UIで失ってはいけない体験:

* 全面画像
* 中央に大きく表示される体験タイトル
* 左上の時計アイコン
* 時刻表示
* 縦に並ぶタイムラインカード
* 画像とタイトルだけで「いつ・誰が・何をした」が伝わること
* 旅行前はワクワクする計画画面になること
* 旅行後は思い出を振り返るMemory画面になること

これは、すべてのカードを別の保存モデルにするという意味ではない。保存モデルはExperienceに寄せ、UI向け表現がExperience Cardとして振る舞える必要があるという意味である。

---

## Spot As Experience

これまでSpotと呼んでいたものは、Travel UIでは単なる場所ではないことが多い。

体験タイトルの例:

* 朝散歩
* オルカショーでずぶ濡れ
* オルカ見ながらビュッフェ
* もう一回オルカ
* 初めての海

ユーザーが見るカードは、Place CardよりExperience Cardに近い。

例:

* `place_name`: マリンワールド
* `display_title`: オルカショーでずぶ濡れ

domain / API / MCP / ToolではExperienceを正規名にする。DB / 既存互換ではTimeline Itemという名前を残す。重要なのは、Experienceが場所だけでなく体験を表現できることである。

分離候補のフィールド:

* `title`: Toolや要約でも使う標準タイトル
* `display_title`: UI向けの体験タイトル
* `place_name`: 物理的な場所名
* `experience_type`: `spot`, `move`, `event`, `memo`
* `item_type`: 既存互換名。値は`experience_type`と同じ

既存データでタイトルが1つしかない場合は、それを`display_title`として扱ってよい。場所名と体験タイトルが異なる場合、UIのカードタイトルには`display_title`を優先し、`place_name`は補助情報として保持する。

---

## Cover Image

Cover ImageはTravel UI体験の中心である。

旅行前は、Google Places由来の仮画像によって計画が具体的になり、ワクワク感を作れる。旅行後は、Photo Skillから選んだ家族写真へ置き換えることで、Memoryとしての価値が高まる場合がある。

ただし、家族写真への置き換えは必須ではない。Google仮画像のままでも、計画や思い出の体験を十分に伝えられる場合はそのままでよい。

Cover Imageのsource例:

* Google Places由来の仮画像
* ローカルキャッシュ済みのGoogle Places画像
* Photo Skill経由で選んだ家族写真
* 手動指定の画像参照

画像は、体験を素早く理解するための情報である。Memory用途では特に、家族写真がTimelineと当時の子どもの年齢や反応を結びつける。

---

## Memoryとの関係

Memoryは、必ずしも最初から別Entityである必要はない。

以下が揃っている場合、Spot、Event、Move、Timeline Item自体がMemoryとして機能する。

* 写真
* メモ
* 時刻
* タイトルまたは表示タイトル
* 参加者や家族文脈

旅行後には、同じTimelineカードが「予定していた体験」から「思い出として振り返る体験」へ変わる。独立したMemory Entityは、共有範囲、複数写真、独立した要約、ハイライト選択が必要になった時に使えばよい。

---

## UIとToolの境界

この見た目のルールはWeb UI向けである。

Web UIでは、必要に応じて時計アイコン、大きな中央タイトル、全面画像、縦に流れるカードを保つ。MCP Tool、Chat、APIでは、それらの視覚要素を返したり描画したりする必要はない。

ただし、Tool/APIはUIが体験を再現できるだけのデータを返せる必要がある。

必要なデータ例:

* `title`
* `display_title`
* `start_time`
* `end_time`
* `cover_image`
* `experience_type`
* `participants`
* `memo`
* `linked_photos`
* `place_name`
* `status`
* `planned_start_at`
* `actual_start_at`

これにより、TravelデータはWeb UI、API、MCP Tool、Jarvis Coreから利用でき、UIだけの描画ルールをドメインモデルへ混ぜずに済む。

---

## 設計への影響

今後のDB/API設計では、以下を前提にする。

* Spotを物理的な場所だけだと決めつけない。
* 必要に応じて、物理的な場所名とユーザー向け体験タイトルを分ける。
* Timelineレスポンスには、Experience Cardを再現できるタイトル、時刻、画像、参加者、メモ、写真リンクを含められるようにする。
* Cover Imageは、計画時の仮画像と旅行後の家族写真置き換えの両方を扱えるようにする。
* Memoryは、最初から必ず別Entityにしなくてもよい。十分な情報を持つExperienceがMemoryとして機能する場合がある。
* UI表示要件を、MCP Tool、Chat、APIの必須描画仕様にしない。
