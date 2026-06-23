# Lessons Learned

## Lesson 0001

### テーマ

旅行アプリの増改築

### 状況

旅行アプリを開発する中で、多くの機能追加を行った。

* Spot
* Move
* Immich
* Hero Image
* Timeline
* Logical Delete

など。

### 課題

最初は旅行アプリだけを想定していたため、将来の拡張を十分考慮していなかった。

### 学び

機能中心ではなく、AI中心で設計する。

### 次への反映

Jarvis Coreを先に設計する。

---

## Lesson 0002

### テーマ

思いつきは消える

### 状況

開発中に多くのアイデアが生まれる。

* 家電操作
* 写真表示
* 音楽
* 家庭菜園
* 音声操作

など。

### 課題

思いつきを頭の中だけで管理すると忘れる。

### 学び

今すぐ実装しなくても良い。

忘れない仕組みを作る。

### 次への反映

Idea Backlogを管理する。

---

## Lesson 0003

### テーマ

AI時代の設計

### 状況

AIはコード修正が得意になってきた。

### 課題

土台が複雑だとAIも苦労する。

### 学び

未来のAIのために設計する。

### 次への反映

モジュール化
Tool化
Decision Log管理

を行う。

---

## Lesson 0004

### テーマ

人格とは何か

### 状況

Jarvisに人格を持たせたいと考えた。

### 学び

人格は口調ではない。

人格は

* Vision
* Decision
* Memory
* Lessons

から形成される。

### 次への反映

Jarvisは会話だけでなく経験を蓄積する。

---

## Lesson 0005

### テーマ

人間とAIの役割

### 状況

将来的にはAIによる自己拡張を目指す。

### 学び

現在は人間承認型が適している。

将来はAIの自律性を高める。

### 次への反映

まずは

AI
↓
提案
↓
人間承認

から始める。

---

## Lesson 0006

### テーマ

Safari Firstの必要性

### 状況

Jarvis Shell v0.1でSafari問題が再発した。

Chromeでは動いても、iPhone / Safariで動かないfrontendはJarvisの主要利用端末で未完成になる。

### 原因

`frontend/static/shell.js` の `Array.prototype.flatMap` がSafariで問題になった。

`shell.js` import時に例外が起きると、`app.js` の初期化が止まり、Developer UI / Runtime UI も巻き込んで止まる構造になっていた。

### 対策

`shell.js` を直接読み込み、自身で初期化する構造に寄せた。

また、Safari-safeな `var` / `function` / plain object 中心の実装へ寄せた。

### 学び

新規frontend JSでは、`flatMap` などSafari互換上の不安がある構文やAPIを不用意に使わない。

import先のトップレベル例外でアプリ全体を止めない。

Shell / Runtime Execute / Developer UI の初期化はできるだけ分離し、一部の失敗が全体停止にならない構造にする。

### 次への反映

Safari First / Safari-safe Frontend を設計原則として明文化する。

新規frontend JS追加時は、Safariでの実機確認を必須チェックに含める。
