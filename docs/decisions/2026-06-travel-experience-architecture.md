# Decision: Travel Experience Architecture

## 日付

2026-06

---

## Background

Travel Skillは当初、以下のような旅行計画中心のモデルだった。

```text
Trip
 ├ Spot
 └ Move
```

しかし、実際に家族が旅行やおでかけの記憶として振り返るのは、行った場所だけではない。

* 行った場所
* 移動
* 出来事
* メモ
* 写真

これらをまとめた「体験」が記憶の単位である。Spot中心のモデルでは、移動中の出来事、場所に紐付かないイベント、短いメモ、写真を伴う思い出を例外として扱う必要があり、実際の利用モデルと一致しなかった。

また、Jarvis Coreからの操作も、「Spotを追加」だけを正規操作にするより、以下のようにExperienceを対象にする方が自然である。

* 体験を追加
* 体験を編集
* 写真を体験へ紐付け

このため、旅行計画の構成要素ではなく、家族が記憶する単位をTravel Skillの正規概念にする必要がある。

---

## Decision

Travel Skillの正規概念は `Experience` とする。

Spotは独立したEntityではなく、Experience Typeの一つとして扱う。

Experience Typeは以下とする。

* `spot`
* `move`
* `event`
* `memo`

これにより、場所、移動、出来事、メモを同じライフサイクルとAPIで扱い、写真や将来の参加者、タグ、感情などを一貫してExperienceへ関連付けられる。

Timelineは保存Entityではない。TimelineはExperienceを時刻や手動順序に従って時系列に並べたViewである。

当面は既存互換性と段階的移行を優先し、保存実体として `travel_timeline_items` を利用する。DB上の保存先は維持するが、Domain、API、Toolでの正規名はExperienceとする。

```text
travel_timeline_items（保存実体）
             ↓
        Experience（Domain）
             ↓
         Timeline（View）
```

---

## Photo Model

PhotoはTravel Skillが所有しない。写真データの所有者はPhoto Skillとする。

Travel Skillは以下の参照関係だけを持つ。

```text
Experience
    ↓
Photo Link
    ↓
Photo Skill
```

Experienceには、Photo Skillが管理する写真への参照と、`linked`、`cover` などの関連種別だけを保持する。

代表画像という選択と文脈はExperienceに属する。一方で、写真Asset、実データ、Thumbnail、検索、保存先、外部写真基盤との連携はPhoto Skillが管理する。

この分離により、Travel Skillは写真基盤の実装詳細に依存せず、Photo Skillは旅行以外の家族写真も同じ責務で管理できる。

---

## API Design

Canonical API / Toolは以下とする。

* `create_experience`
* `get_experience`
* `update_experience`
* `archive_experience`
* `get_experience_photos`
* `get_experience_photo_search`

`get_spot`、`create_timeline_item` などの旧API / Toolは既存利用者のための互換APIとして残す。ただし、新規実装とJarvis Coreからの正規呼び出しはExperience APIへ寄せる。

互換APIは内部でExperienceへ変換し、SpotやTimeline Itemを別の正規Domain Entityとして増やさない。

---

## UI Design

UIでは以下の構造を採用する。

```text
Trip
  ↓
Timeline
  ↓
Experience Card
```

TimelineはExperienceの時系列Viewを表示し、Experience Cardはtypeに応じて場所、移動、出来事、メモを表現する。

利用者に分かりやすい場合は、UI上で「Spot」や「場所」と表示してよい。ただし、それは `spot` typeの表示表現であり、内部設計と操作境界はExperience中心とする。UI固有の状態をDomainの正規モデルにはしない。

---

## Future

今後、Experienceを中心に以下を追加する。

* Experience並び替え
* AIによるExperience自動生成
* Experience Participant
* Experience Tag
* Experience Emotion
* Experience Recommendation
* Memory Timeline

Travel Skillは単なる「旅行管理」ではなく、家族のおでかけと記憶を扱う `Family Outing Memory Skill` として発展させる。

---

## 影響

この決定はDomain、API、Tool、UIで使う正規概念を定めるものである。現時点では既存の `travel_timeline_items` と互換APIを維持するため、DB移行や既存クライアントの即時変更は要求しない。

新規機能はExperienceを基準に設計し、Timelineは保存先ではなく取得・表示のViewとして扱う。Photoとの連携では写真データをTravelへ複製せず、Photo Linkを介して参照する。

---

## Jarvis Principle Check

1. Web UIから利用できるか
   * 利用できる。Trip配下のTimelineにExperience Cardとして表示・操作できる。
2. API / Toolとして利用できるか
   * 利用できる。Experience CRUDと写真取得・検索をCanonical API / Toolとして定義する。
3. 将来MCP Tool化できるか
   * できる。Experience IDを境界に、UIから独立した入出力として公開できる。
4. Jarvis Coreから呼び出せるか
   * 呼び出せる。「体験を追加・編集」「写真を体験へ紐付け」という操作に対応できる。
5. UI依存のロジックになっていないか
   * なっていない。TimelineはView、Experience Cardは表示表現であり、正規DomainはExperienceである。
6. 読み取り系か更新系か
   * 両方を含む。取得・写真検索は読み取り系、作成・更新・アーカイブ・写真リンク変更は更新系である。
7. 副作用・権限・プライバシー上の注意はあるか
   * ある。更新系は確認・権限・監査が必要であり、家族写真、位置、時刻、参加者情報はPhoto Skillとの境界を含めて公開範囲を制御する必要がある。
