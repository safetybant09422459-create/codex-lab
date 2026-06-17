# Development Checklist

## Before Coding

* この機能はWeb UIから使えるか
* API / Toolとして切り出せるか
* 将来MCP Tool化できるか
* Jarvis Coreから呼び出せるか
* 入力と出力は明確か
* 読み取り系か更新系か
* 副作用はあるか
* 人間の確認が必要か
* 権限・プライバシー上の問題はあるか
* UIにロジックを閉じ込めていないか

## During Coding

* UIとロジックを分離しているか
* API名 / Tool名が自然か
* エラー時に説明できるか
* Audit Logに残すべきか判断したか

## After Coding

* Web UIで確認したか
* APIとして呼べるか
* 将来MCP化する時の入口が分かるか
* Risk levelを判断したか
* 変更内容をdecision_log.mdに残すべきか判断したか
