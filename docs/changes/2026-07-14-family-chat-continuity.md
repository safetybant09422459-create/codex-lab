# Family Chat Continuity / Trust UX

## 実施日時

2026-07-14（Asia/Tokyo）

## 変更内容

Jarvis ScreenのChat入口を、家族が話し方を学ばなくても始められ、同じタブを再読み込みしても直近の会話を
続けられ、必要なら一操作で消せる体験へ変更した。

* welcome文を機能説明中心から、短い期待値と自然な問いかけへ変更した。
* 固有データを前提にした固定promptを、目的ベースの会話starterへ置き換えた。
* `sessionStorage`へsession IDと最大5件のuser / assistant発話だけを一時保存する。
* 復元した履歴は既存`conversation_history`契約でLLM contextへ渡し、UIで意味解釈しない。
  server stateが空のときだけ`client_history_hint`として使い、trusted action / Observation / entityには昇格させない。
* 「会話を消す」を追加し、Browser状態だけでなく`POST /api/chat/session/reset`からserver-sideのbounded working
  contextも削除する。
* 保存範囲と、長期Memoryへ自動保存しないことを画面上に明示した。
* process-local Conversation Stateへ24時間の無操作TTL、最大256 session、LRU evictionを追加した。
* Chat transport errorを安全な家族向け文言へ変換し、network / timeout / rate limit / 5xxだけに再試行導線を追加した。
  Chat APIは`X-Jarvis-Error-Code`で`chat_not_configured`と`chat_turn_failed`を文字列解析なしに区別する。
* private-by-defaultとして全`/api/` responseへ`Cache-Control: no-store`、全responseへ`X-Content-Type-Options: nosniff`と
  `Referrer-Policy: no-referrer`を追加した。
* Browserのscript / style / image / connect先をself中心へ限定するContent Security Policyを追加した。
* Chat送信中の`aria-busy`、失敗時のalert role、`prefers-reduced-motion`を追加した。

## 変更理由と判断理由

毎日使う理由を作る前に、毎回会話が消える摩擦、何を話せばよいか分からない空白、会話がどこへ保存されるか
分からない不安を減らす必要がある。CalendarやHomeを急いで追加しても、入口への信頼と継続性が低いままでは
日常利用につながりにくい。

この変更はConversation StateをMemoryへ昇格させず、Channelの一時表示状態とCore-owned bounded working contextを
同じsession IDで接続する。starterはLLMへの通常発話として送るだけで、UIがProvider / Operationを選択しない。
したがってAI First、Provider Principle、Trust Before Automationを維持する。

各sessionのturn数だけを制限しても、session数が無制限なら長期稼働中に一時状態が蓄積する。TTLとLRUは発話内容を
解釈せず、時間と容量だけで決定的に削除するため、Python Brainを追加せずprivacyと運用安定性を高める。

失敗時はHTTP / network状態だけを表示契約へ変換する。Providerやユーザー意図を推測せず、再実行して安全なChat
requestだけを再試行候補にする。response headerは認証・visibilityの代替にせず、cache残留を減らす多層防御とする。

## 参考にしたもの

* Apple Human Interface Guidelines / Generative AI: AI利用、能力・制約、privacyの透明性と、open-ended promptの
  curated suggestion。
* Google Conversation Design / Greetings: welcome、期待値、ユーザーへ主導権を返す短い導入。
* Google Conversation Design / Commands: 特定commandを暗記させず、ユーザーが達成できる目的を示す。
* Google Conversation Design / Confirmations: 理解・実行のfeedbackにより訂正可能性と信頼を高める考え方。
* WAI-ARIA 1.2 / W3C ARIA19: live region更新中の`aria-busy`と、動的errorを通知する`role=alert`。
* MDN Cache-Control / Referrer Policy: 個人化responseのshared cache漏えい防止とreferrer最小化。

これらのUIをコピーせず、JarvisのProvider中立なChat、bounded state、Memory非自動保存という既存境界へ適用した。

## 検討した代替案

### 採用案

tab-scoped continuity + explicit clearを採用した。DB migrationなしで即時価値があり、Safariのstorage失敗時も
in-memory会話へ安全に縮退できる。server resetはidempotentで、RuntimeやProviderへUI固有条件を漏らさない。
bounded lifecycle、transport-aware recovery、private response policyも採用した。いずれも自然言語の意味判断ではなく、
決定的なChannel / Runtime周辺責務として実装できる。

### 不採用案

* 固定Todayダッシュボード: 現在のCalendar / Weather / Home Evidenceが不足し、UIやPythonへ固定priorityと
  意味判断を持ち込みやすいため見送った。
* 会話全文のDB永続化: household / member、visibility、retention、forget、暗号化の契約前に実装するとPrivacy
  Firstを損なうため見送った。
* starterからOperationを直接実行: Catalog PrincipleとRuntime境界を迂回するため採用しなかった。
* Browser localStorageによる長期保存: 共有端末で会話が残り続けるため採用しなかった。

### 将来案

* 認証済みprincipalとvisibilityを持つConversation Repository。
* 保存期間・端末・家族共有範囲を選べるPrivacy Center。
* LLM / Coreが選択したDashboard Presentation Contract。
* 明示確認されたMemory CandidateだけをMemory Providerへ保存するflow。

## 影響範囲

* Web Chatの初期表示、直近会話復元、clear操作。
* Agent Hostのprocess-local conversation store。
* `POST /api/chat/session/reset` API。
* Chat API clientのerror contractとWeb Chatの再試行表示。
* Chat / Travel / Photo / Runtime / Developer APIのcache policy。

Travel、Photo、Runtime、Provider Operation、Permission / Confirmation / Audit契約は変更しない。保存データはsession ID、
role、最大5件の発話だけで、Tool result、Observation、写真、位置、secretはBrowser storageへ追加しない。

## デメリットとリスク

* sessionStorageは同じtab内だけであり、別端末・別tabへは継続しない。
* TTLはprocess-localで、複数process間の統一retentionではない。
* server再起動後はBrowser履歴が表示されても、server-side active entity等は消えている。既存のbounded
  `conversation_history`が会話材料を補うが、完全な状態復元ではない。
* XSSが存在すればsessionStorageを読まれるため、将来のCSPとfrontend security reviewが必要。
  今回self-only CSPを追加したが、DOM生成箇所の継続reviewは必要である。
* CSPは将来の外部font、Voice、Camera、Browser直結Providerを既定で拒否する。追加時はdirectiveの明示reviewが必要。
* 未認証段階では、Browserの暗号学的乱数を優先して生成する推測困難なsession IDが境界であり、本格的な
  ユーザー分離ではない。

## ロールバック方法

DB変更はない。frontendのsessionStorage / clear UI、reset endpoint、`clear_session`を戻せば従来のreload時に消える
process-local Chatへ戻る。Browserに残る`jarvis.chat.working-context.v1`はsession終了時に消え、必要ならDeveloper
ToolsからではなくBrowserのsite data消去で削除できる。

TTL / LRUは`InMemoryConversationStateStore`のconstructor既定値を従来相当へ戻せば無効化できる。response middlewareと
`ApiError` / retry renderer、security header middlewareは独立して戻せる。永続データやmigrationのrollbackは不要である。
