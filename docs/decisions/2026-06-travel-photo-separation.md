# Decision: Travel Photo Separation

## 日付

2026-06

---

## テーマ

Travel Skill実装前に、Travel、Photo、Google Placesの責務境界を整理する。

既存の旅行アプリはJarvis構想より前に作られており、Travel、Spot、Immich、Photo管理が強く結びついている。

このままTravel Executorを実装すると、将来の責務分離が難しくなる可能性がある。

---

## 決定

TravelとPhotoを分離する。

Travelは旅行や日帰りのおでかけの計画と記憶を扱う。

Photoは写真を扱う。

TravelはPhotoを利用することはあるが、写真そのものを管理しない。

TravelはImmichを知らない。

Immichとの通信や写真基盤の管理はPhotoが担当する。

現時点ではPlace Skillを作らない。

Google PlacesはGoogle Places Adapterとして扱う。

Spot代表画像はPhotoではなく、TravelとGoogle Places Adapterの責務として扱う。

Trip代表画像も同じくTravelとGoogle Places Adapterの責務として扱う。Google Places由来の仮画像はPhoto Assetではなく、旅行後に家族写真へ置き換える場合だけPhoto SkillのAsset参照をTravelが採用する。

---

## 1. TravelとPhotoを分離した理由

TravelとPhotoは扱う中心が違う。

Travelは家族旅行、日帰りのおでかけ、近場イベントを含む「家族のおでかけ記憶」を扱う。

主な対象は以下である。

* Wishlist
* Trip / Outing
* Participants
* Candidate Spot
* Spot
* Move
* Event
* Timeline Item
* Reservation
* Memo
* Cover Image
* Photo Link
* Memory
* Checklist
* Packing
* Budget
* Review

Checklist、Packing、Budgetは補助機能である。Travelの核は、候補を家族で相談し、Timelineを作り、旅行後に写真と思い出メモをMemoryとして見返すことにある。

Photoは家族の写真基盤を扱う。

主な対象は以下である。

* Asset
* Album
* Search
* Thumbnail
* Immich Adapter

旅行写真はPhotoの一部であるが、写真全体はTravelの一部ではない。

家族写真には、日常、学校行事、誕生日、家での写真、旅行以外のイベントも含まれる。

PhotoをTravelに含めると、旅行以外の写真利用がTravelの文脈に引きずられる。

逆にTravelをPhotoに寄せると、旅行計画、移動、予約、持ち物、予算などが写真管理の中に入り込む。

どちらもJarvisのSkillとして独立可能であるべきであり、Jarvis PrincipleのModule Independenceに反する構造を避ける必要がある。

したがって、TravelとPhotoは分離する。

---

## 2. TravelがImmichを持たない理由

Immichは写真管理基盤であり、旅行ドメインそのものではない。

TravelがImmichを直接扱うと、Travelの設計がImmichのAPI、ID、Album構造、検索仕様に依存する。

その結果、以下の問題が起きる。

* Travel Executorが写真サービスの実装詳細を知る
* Immich以外へ移行する時にTravelを変更する必要がある
* 旅行データと写真データの境界が曖昧になる
* 家族写真のプライバシー制御がTravel側に漏れる
* MCP Tool化した時にTravel Toolの責務が広がりすぎる

Travelが必要なのは、Immichそのものではない。

Travelが必要なのは、以下のような要求である。

```text
この旅行に関連する写真を取得したい
このSpot周辺で撮影された写真候補を見たい
旅行Memoryに使える写真候補を出したい
```

この要求はPhoto Skillに対して行う。

Photo Skillが内部でImmich Adapterを使う。

TravelはImmichを知らず、Photoの抽象化されたToolやAPIを使う。

TravelがMemoryやCover Image置き換えのために写真候補を必要とする場合も同じである。TravelはPhotoへ時間帯、位置、Trip、Spot、Move、Eventなどの条件を渡し、PhotoはAsset候補と権限情報を返す。

---

## 3. Place Skillを作らなかった理由

現時点ではPlace Skillを作らない。

Placeは便利な抽象に見えるが、責務が集まりやすい。

Place Skillを作ると、以下の領域が集まりやすくなる。

* TravelのSpot
* Calendarの場所
* Navigationの目的地
* Weatherの地点
* Homeの住所や拠点
* Photoの撮影場所

これらはすべて「場所」に関係するが、同じ責務ではない。

旅行のSpot、天気の地点、家の住所、写真のGPS、カレンダーの開催場所は、それぞれ違う文脈を持つ。

今の段階でPlace Skillを作ると、利用用途がまだ限定的なのに抽象化だけが先に進む。

早すぎる抽象化は、後から本当に必要な境界を見えにくくする。

したがって、現時点ではPlace Skillを作らない。

まずはTravelが必要とするGoogle Places連携だけをAdapterとして扱い、他Skillからの利用が増えた時にPlace Skill化を再検討する。

---

## 4. Google Places Adapter採用理由

Google Placesは、TravelのSpot作成やSpot代表画像に必要である。

ただし、Google Places APIは外部サービスであり、Travelのドメインモデルではない。

Google Places Adapterを採用する理由:

* TravelがGoogle APIレスポンスに依存しないようにするため
* APIキー、課金、レート制限、エラー処理をAdapterに閉じ込めるため
* Google Places以外のProviderへ移行しやすくするため
* テストやstub実行をしやすくするため
* Spotモデルを外部APIの仕様変更から守るため
* MCP Tool化時に外部API境界を説明しやすくするため

Adapterが担当する操作:

* `search_place_candidates`
* `get_place_details`
* `get_place_photos`
* `cache_place_photo`

Travelは、場所候補や代表画像候補を取得するためにAdapterを利用する。

TravelはGoogle Places APIを直接呼ばない。

---

## 5. Spot代表画像をPhotoに入れなかった理由

Spot代表画像は、TravelのSpotを見やすくするための画像である。Trip代表画像も、Trip / Outingのトップ画面で家族が見返しやすくするための画像である。

現在の旅行アプリでは、Spot代表画像としてGoogle Placesの画像を利用している。

これはImmichに保存された家族写真ではない。

Photo Skillに入れるべき写真は、Asset、Album、Search、Thumbnail、Immich Adapterの対象になる写真である。

Google Places画像は外部Place情報であり、家族の写真Assetではない。

Google Places由来のCover ImageをPhotoに入れると、以下の問題が起きる。

* Immich写真とGoogle Places画像の意味が混ざる
* 家族写真の権限管理と外部Place画像の扱いが混在する
* TravelのSpot表示都合がPhotoに入り込む
* Photoが旅行計画中の外部画像まで責務に持つ

Trip代表画像やSpot代表画像は、訪問前にも必要になる。

訪問前には、まだ家族写真は存在しない。

そのため、Google Places由来のCover ImageはTravelの表示文脈の一部として扱い、画像取得とキャッシュはGoogle Places Adapterに委譲する。

Photoは、旅行後に撮影された家族写真やAlbumを扱う。

旅行後にGoogle仮画像を実際の家族写真へ置き換える場合、TravelはPhoto SkillのAsset参照をCover Imageとして採用する。ただし、Asset保存、Thumbnail、Immich連携はPhoto側に残す。

---

## 影響

今後Travel Executorを実装する場合、以下を前提にする。

* Travel ExecutorはImmichを直接呼ばない
* Travel ExecutorはPhoto SkillのToolまたはAPIへ問い合わせる
* Travel ExecutorはGoogle Places Adapterを経由してPlace情報を取得する
* Trip代表画像とSpot代表画像はPhoto Assetとは別に扱う
* Memory用の写真候補はPhoto Skillへ問い合わせる
* Place Skillはまだ作らない

この判断により、初期実装は少し遠回りになる。

ただし、将来のMCP Tool化、家族写真のプライバシー管理、外部API交換可能性を考えると、責務を分けてからTravel実装へ進む方が安全である。

---

## 再検討条件

以下の条件が増えた場合、Place Skill化を再検討する。

* Travel以外の複数SkillがPlace検索を必要とする
* Calendar、Navigation、Weather、Homeで共通のPlaceモデルが必要になる
* Google Places以外のProviderを複数扱う必要が出る
* Placeの正規化、重複排除、履歴管理が独立した責務になる

Photoとの境界は、Immich以外の写真基盤へ移行する場合にも維持する。

Photoは写真を扱い、Travelは旅行やおでかけの計画と記憶を扱う。
