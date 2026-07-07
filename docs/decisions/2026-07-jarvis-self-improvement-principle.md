# Decision: Jarvis Self-Improvement Principle

## 日付

2026-07-08

## Status

Accepted（設計原則。Learning Logの保存・review・retrieval・自動実行は未実装）

## 背景

ProviderはRecordとSource of Truth、Observationは今回の会話で得た観測事実、Long-term Contextは未来の推論を
変える長期文脈を扱う。Conversationや作業ログはretention policyに従って一定期間で削除できる一方、失敗や
ユーザー訂正はJarvisの設計改善へ活用する価値がある。

しかし失敗、頓珍漢な回答、選択ミスをLong-term Contextへ保存すると、Jarvis自身の問題をユーザーの好み、性格、
方針として扱い、未来の通常回答を誤らせる。この誤学習を防ぎつつ改善シグナルを残すため、用途と参照経路を分離する。

## 決定

**Jarvisは失敗をLong-term Contextとして覚えない。**

Long-term ContextとLearning Logを次のように分離する。

| 区分 | 目的 | 通常回答での利用 |
| --- | --- | --- |
| Long-term Context | ユーザー理解と、長期間にわたり未来の推論を変える文脈 | visibility、permission、token budget内の候補をLLMが判断して利用できる |
| Learning Log | Jarvis自身の改善材料、設計改善提案、責務・説明・Context改善候補 | 利用しない。Jarvis改善レビュー時だけ参照する |

Learning Logには、失敗、ユーザー訂正、頓珍漢な回答、Provider選択ミス、Operation選択ミス、Runtime失敗、
Context不足、Provider責務の曖昧さを改善シグナルとして扱える。これはユーザー理解ではなく、Jarvis自身の
設計・契約・文脈提供を見直す材料である。

### 重要な分離

* 失敗や改善シグナルをLong-term Contextへ混ぜない。
* Learning Logを通常回答の根拠にしない。
* Learning Logをユーザーの好み、性格、方針として扱わない。
* Learning LogはJarvis改善時だけ参照する。
* ProviderのRecord / Source of Truth、Observation、Conversation Stateの責務をLearning Logで代替しない。

## Self-Improvementの流れ

1. Conversation、Runtime、Observation、User correctionから、失敗または改善シグナルの候補を残す。
2. Conversationや作業ログそのものはretention policyに従って一定期間で削除できる。
3. 必要最小限にredactionした失敗、訂正、改善シグナルはLearning Logとして保持できる。
4. LLMがLearning Logを定期または条件付きでレビューする。
5. LLMはProvider Responsibility、Capability説明、Operation説明、Context Assembly、Long-term Context retrieval、
   新Provider候補の改善を提案できる。
6. Provider生成、DB作成、API追加、Tool追加、コード変更は人間が判断する。

改善シグナルの意味判定はLLMが行う。PythonはRuntimeの構造化された失敗状態等を決定的に記録できるが、会話や
訂正を解釈して失敗カテゴリ、原因、改善策を決めない。

## 自動化の境界

自動で行ってよいこと:

* Learning Logへ失敗・訂正・改善シグナルを記録する。
* Learning Logを要約する。
* Learning Logから改善提案を作る。
* 改善候補をdocsやreview対象として提示する。

自動で行ってはいけないこと:

* Providerを生成する。
* DBを作成する。
* API / Toolを追加する。
* コードを変更する。
* Long-term Contextへ失敗を混ぜる。
* Learning Logを根拠に通常回答する。
* 失敗をユーザーの性格、好み、方針として保存する。

自動化が許される「記録」は、事前に定義されたvisibility、permission、retention、redaction、監査の範囲内に限る。
改善提案は実行許可ではなく、人間が内容、影響、権限、migration、privacyをレビューする対象である。

## 棚卸し方針

* Conversationや作業ログは一定期間で削除できる。
* Providerが管理するRecordはLearning Logの棚卸しを理由に削除しない。
* Long-term Contextは肥大化した場合に棚卸しする。
* Learning Logは失敗、訂正、改善シグナルとして保持できる。
* 棚卸しは毎日必須とせず、年単位、サイズ超過、明確な改善候補が増えた時に実施できる。
* 例として、Long-term Contextが100KBを超えた時を棚卸し開始の決定的な閾値候補にできる。

サイズや期間による対象抽出はPythonで決定的に行える。何を重要な文脈または改善シグナルとして残すか、統合するか、
削除候補にするかという意味判断はLLMまたは人間が行う。具体的な閾値、保存期間、削除契約は実装前に別途決定する。

## Python Brain Regressionとの関係

Pythonが担当できるもの:

* 保存
* Long-term Context、Learning Log、Record、Observation、Conversation Stateの分離
* visibility、permission、retention、redaction、token budgetの決定的policy適用
* schemaに基づく決定的な構造化
* Runtime状態と失敗結果の記録

Pythonが担当してはいけないもの:

* 自然言語からの失敗意味判定
* 改善提案生成
* Provider化判断
* Learning Logからユーザー理解への変換
* Learning Logを通常回答へ利用するかの判断

これらの意味判断はLLMが担う。ただしLLMの提案もProvider、DB、API、Tool、コードを変更する権限にはならない。

## 理由

ユーザー理解とJarvis自身の改善材料を分けることで、失敗を将来回答へ混入させず、訂正や障害から設計上の弱点を
継続的に見つけられる。さらに、記録・提案と実装を分離することで、自己改善をTrust Before Automation、
Runtime safety、Python Brain Regression Guardと両立できる。

## 非対象

* Learning LogのDB、schema、API、Tool、Provider、保存形式
* Learning Logのretrieval、RAG、embedding、ranking
* 失敗検出、分類、要約、定期reviewの実装
* Long-term Context retrievalまたは棚卸し処理の実装
* Provider生成、DB migration、API / Tool追加、コード変更

## 再検討条件

Learning Logを通常回答から分離したまま改善reviewへ安全に提供できない具体例、または人間判断なしでは有効な改善を
進められないため提案境界自体を変更すべき具体例が得られた場合に再検討する。保存技術やデータ量だけを理由に、
Learning LogをLong-term Contextへ統合しない。

## Jarvis Principle Check

1. Web UIから利用できるか: 未実装。将来は改善候補のreview入口になり得るが、通常Chatの根拠にはしない。
2. API / Toolとして利用できるか: 未実装。本DecisionはAPI / Tool契約を追加しない。
3. 将来MCP Tool化できるか: review用read契約は候補になり得るが、変更実行権限とは分離する。
4. Jarvis Coreから呼び出せるか: 将来、改善review時だけCore / LLMへ提供できる。通常のContext Assemblyには入れない。
5. UI依存のロジックになっていないか: なっていない。記録、review、提案の境界はChannel非依存である。
6. 読み取り系か更新系か: 本Decisionはdocsのみ。将来の記録は更新系、要約・reviewは読み取り系として別途設計する。
7. 副作用・権限・プライバシー上の注意: 会話、訂正、失敗には家族情報や秘密が含まれ得るため、最小記録、visibility、permission、retention、redaction、監査、人間確認が必要である。
