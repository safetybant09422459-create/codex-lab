# Google Places Adapter

## 目的

Google Places Adapterは、Google Places APIをJarvis内で利用するためのAdapterである。

現時点ではPlace Skillは作らず、Travelが必要とする場所検索、場所詳細、場所画像、画像キャッシュをAdapterとして扱う。

Travelは家族旅行だけでなく日帰りのおでかけも扱う。Google Places Adapterは、その計画時に使うCandidate Spot検索とCover Image候補取得を支える。

TravelはGoogle Places APIを直接呼ばない。

---

## 対象

Google Places Adapterが扱う主な操作:

* `search_place_candidates`
* `get_place_details`
* `get_place_photos`
* `cache_place_photo`

これらはTravelのCandidate Spot作成、Spot代表画像選択、Trip代表画像選択を支える。

---

## 責務

Google Places Adapterの責務:

* キーワードや位置情報からPlace候補を検索する
* Google PlacesのPlace詳細を取得する
* Placeに紐づく画像情報を取得する
* Place画像をキャッシュする
* APIレスポンスをJarvis向けに正規化する
* Google APIキーや認証情報を隠蔽する
* レート制限やエラーをAdapter内で扱う
* Google固有のID、URL、画像参照をTravelから隠す
* Trip代表画像やSpot代表画像に使える画像参照を返す

Google Places Adapterは、Google Placesを使うための境界であり、旅行そのものの判断は行わない。

---

## 非責務

Google Places Adapterが扱わないもの:

* Tripの作成・更新
* Candidate Spotの最終採用判断
* 家族旅行としての優先度判断
* Reservation管理
* Move管理
* Photo Asset管理
* Immich連携
* 家族写真Album管理
* Calendar予定管理
* Navigation経路管理
* Weather判断

Adapterは外部API連携に集中する。

Travelが「家族旅行に使うか」を判断し、Adapterは「Google Placesから必要な情報を取る」ことに集中する。

---

## Travelが直接Google APIを呼ばない理由

TravelがGoogle Places APIを直接呼ばない理由:

* TravelをGoogle固有のレスポンス構造に依存させないため
* APIキー、レート制限、課金、エラー処理をTravelから分離するため
* Google Places以外のPlace Providerへ移行しやすくするため
* Spotのドメインモデルを外部APIの都合から守るため
* テスト時にAdapterをstub化しやすくするため
* MCP Tool化した時に、外部API境界を明確にできるため

Travelは以下のような抽象的な要求だけを行う。

```text
このSpot名に近いPlace候補を探したい
このPlaceの詳細を取得したい
このSpotの代表画像候補を取得したい
```

Google APIの呼び出し方法、レスポンス形式、画像取得手順はAdapterが担当する。

---

## Spot代表画像

現在の旅行アプリでは、Spot代表画像としてGoogle Placesの画像を利用している。Trip代表画像にも同じ考え方を適用できる。

この画像はImmichの写真Assetではない。

したがって、Google Places由来のCover ImageはPhoto Skillではなく、TravelとGoogle Places Adapterの責務として扱う。

理由:

* Trip代表画像やSpot代表画像は旅行計画中にも必要になる
* 訪問前には家族写真が存在しないことが多い
* Google Places画像は外部Place情報であり、家族写真ではない
* Photoに入れると、Immich写真と外部Place画像の意味が混ざる
* Spot表示のための画像選択はTravelの文脈に近い

TravelはTripやSpotに代表画像参照を持てる。

ただし、画像取得、Google photo reference、キャッシュ保存、期限管理はGoogle Places Adapterが担当する。

旅行後に実際の家族写真へ置き換える場合、Photo SkillのAsset参照をTravelが採用する。置き換えずGoogle仮画像のまま残る場合もあり、その状態はTravel側のCover Image状態として表現する。

---

## 操作

### search_place_candidates

場所名、住所、周辺位置などからPlace候補を検索する。

入力例:

* query
* location
* radius
* language

出力例:

* provider
* provider_place_id
* name
* address
* location
* rating
* photo_available

---

### get_place_details

候補から選ばれたPlaceの詳細を取得する。

入力例:

* provider_place_id
* language

出力例:

* name
* address
* location
* opening_hours
* website
* phone_number
* rating
* photo_refs

---

### get_place_photos

Placeに紐づく画像候補を取得する。

入力例:

* provider_place_id
* max_width
* max_height

出力例:

* photo_ref
* width
* height
* attribution
* cache_status

---

### cache_place_photo

Google Places画像をJarvis側で使いやすい形にキャッシュする。

入力例:

* photo_ref
* provider_place_id
* requested_size

出力例:

* cached_url
* expires_at
* attribution
* source

キャッシュは、Googleの利用規約や画像の帰属表示を守る必要がある。

---

## 将来のExecutor候補

Google Places AdapterのExecutor候補:

* `GooglePlacesSearchExecutor`
* `GooglePlacesDetailsExecutor`
* `GooglePlacesPhotoExecutor`
* `GooglePlacesPhotoCacheExecutor`

初期段階ではstubまたは読み取り系から始める。

外部API呼び出しは、APIキー、課金、レート制限、ログに残す情報を整理してから実装する。
