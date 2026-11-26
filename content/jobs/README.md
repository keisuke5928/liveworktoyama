# 求人情報（content/jobs/）

1件1ファイル（`<YYYY-MM-DD>-<会社名の英字>-<職種>.json`）。`status` が `open` で、`checked` から14日以内のものだけがサイトに表示される（build.py が自動で隠す）。

```json
{
  "status": "open",                       // open / closed（募集終了は closed にする。ファイルは消さない）
  "employer_id": "greens",                // content/employers/ のファイル名
  "title": {"en": "...", "easy": "...", "ja": "...", "vi": "...", "id": "..."},
  "employer": {"en": "...", "ja": "株式会社〇〇"},
  "region": "toyama_city",                // ui.json の region_*（toyama_city, takaoka, uozu, namerikawa, kurobe ...）
  "category": "manufacturing",            // manufacturing / care / hotel / food / agriculture / construction / retail / logistics / office / other
  "employment": "full_time",              // full_time / contract / part_time / dispatch
  "pay": {"per": "month", "min": 220000, "max": 250000},   // per: month / hour / day / year。書かれていなければ省略
  "hours": {"en": "...", "ja": "..."},    // 任意
  "japanese": "n3",                       // not_required / basic / n4 / n3 / n2 / n1 / daily / unknown
  "housing": "dorm",                      // dorm / support / none / unknown
  "visa": {"en": "...", "ja": "..."},     // 任意。求人に書かれている在留資格だけ
  "foreign_welcome": {"en": "...", "ja": "求人に「外国籍の方歓迎」と記載"},   // 根拠（どこにどう書かれていたか）
  "summary": {"en": "...", "easy": "...", "ja": "...", "vi": "...", "id": "..."},
  "students_ok": false,                   // 留学生歓迎と書かれている場合だけ true
  "source_url": "https://（企業の公式採用ページ、または公的機関のページ）",
  "source_name": {"en": "... official careers page", "ja": "〇〇 公式採用ページ"},
  "first_listed": "2026-11-26",
  "checked": "2026-11-26",
  "paid": false
}
```

出典は企業の採用ページ、ハローワーク、求人サイト（2026-11-26 オーナー指示）。文章はコピーせず要約し、元の求人へのリンクを必ず付ける。
求人を出している企業は `content/employers/<slug>.json` に企業紹介を作り、求人の `employer_id` にその slug を入れる（形式は既存のファイルを参照）。
