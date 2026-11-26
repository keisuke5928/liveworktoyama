#!/usr/bin/env python3
"""Collect job listings in Toyama tagged "外国人積極採用" (actively hiring foreign nationals) on JobsGo.

Usage: python3 tools/collect_jobs.py            # writes content/jobs_auto/jobsgo.json
       python3 tools/collect_jobs.py --max-pages 3

Only the list pages are read (about 30 listings per page, one request per second).
Nothing is copied except short facts (job title, employer, place, type, pay, hours, dates).
The output is a snapshot: listings that are no longer on JobsGo disappear from the file,
so closed jobs are removed from the site automatically (CLAUDE.md chapter 6).
"""
import datetime
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "content/jobs_auto/jobsgo.json"
LIST_URL = "https://www.jobs-go.jp/toyama/jobs/k9?page={n}"
UA = "Mozilla/5.0 (compatible; LiveWorkToyamaBot/1.0; +https://liveworktoyama.com/about/)"

CITIES = {
    "富山市": "toyama_city", "高岡市": "takaoka", "魚津市": "uozu", "氷見市": "himi", "滑川市": "namerikawa",
    "黒部市": "kurobe", "砺波市": "tonami", "小矢部市": "oyabe", "南砺市": "nanto", "射水市": "imizu",
    "舟橋村": "funahashi", "上市町": "kamiichi", "立山町": "tateyama", "入善町": "nyuzen", "朝日町": "asahi",
}
EMPLOYMENT = [("紹介予定派遣", "dispatch"), ("派遣", "dispatch"), ("契約", "contract"), ("アルバイト", "part_time"),
              ("パート", "part_time"), ("副業", "part_time"), ("正社員", "full_time")]
CATEGORY = [
    ("care", r"介護|看護|福祉|ヘルパー|ケア|保育|生活支援員|デイサービス|老人ホーム|訪問"),
    ("hotel", r"ホテル|旅館|フロント|客室|宿泊"),
    ("food", r"調理|パン|食品|飲食|厨房|給食|惣菜|レストラン|カフェ|食堂|弁当|寿司|製菓"),
    ("agriculture", r"農|漁|畜産|園芸|水産"),
    ("construction", r"施工|建設|土木|大工|塗装工|配管|電気工事|設備工事|解体|左官|鳶|内装|測量|昇降機"),
    ("logistics", r"ドライバー|配送|倉庫|物流|運転手|運送|フォークリフト|ピッキング|仕分"),
    ("manufacturing", r"整備|製造|工場|組立|加工|溶接|成形|検査|オペレーター|機械|部品|金属|樹脂|プレス|研磨|梱包|ライン"),
    ("retail", r"販売|店舗|接客|レジ|スーパー|ショップ|営業"),
    ("office", r"事務|エンジニア|SE|システム|プログラ|IT|設計|経理|総務|通訳|翻訳|教員|講師"),
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "ignore")


def text(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"[ \t　]+", " ", s).strip()


def cell(block, cls):
    m = re.search(r'<tr class="%s">\s*<th>.*?</th>\s*<td>(.*?)</td>' % cls, block, re.S)
    return text(m.group(1)) if m else ""


def parse_pay(s):
    s1 = s.split("\n")[0]
    nums = [int(x.replace(",", "")) for x in re.findall(r"(\d[\d,]*)円", s1)]
    if not nums:
        return None
    per = "month"
    if "時給" in s or max(nums) < 5000:
        per = "hour"
    elif "日給" in s or max(nums) < 40000:
        per = "day"
    elif "年収" in s or "年俸" in s or min(nums) > 1500000:
        per = "year"
    p = {"per": per, "min": nums[0]}
    if len(nums) > 1 and nums[1] >= nums[0]:
        p["max"] = nums[1]
    return p


def parse_hours(s):
    times = re.findall(r"(\d{1,2})時(\d{2})分\s*〜\s*(\d{1,2})時(\d{2})分", s)
    return " / ".join(f"{int(a)}:{b}–{int(c)}:{d}" for a, b, c, d in times[:3])


def parse_block(block):
    m = re.search(r'href="/jobs/detail/([\w-]+)"[^>]*>(.*?)</a>', block, re.S)
    if not m:
        return None
    jid, title = m.group(1), text(m.group(2))
    comp = re.search(r'<span class="job-company">(.*?)</span>', block, re.S)
    comp = text(comp.group(1)) if comp else ""
    employer = re.sub(r"の求人情報.*$", "", comp, flags=re.S).strip()
    employer = re.sub(r"\s+", " ", employer)
    loc = cell(block, "location")
    city = next((v for k, v in CITIES.items() if k in loc or k in comp), None)
    if not city:
        return None  # outside Toyama Prefecture or unknown
    pub = re.search(r"掲載開始日:(\d{4})/(\d{1,2})/(\d{1,2})", block)
    published = f"{pub.group(1)}-{int(pub.group(2)):02d}-{int(pub.group(3)):02d}" if pub else None
    src = re.search(r"情報提供元：([^<\s]+)", block)
    office = src.group(1) if src else ""
    emp_text = cell(block, "requirement")
    tags = " ".join(re.findall(r'class="tag[^"]*"[^>]*>([^<]+)<', block))
    etype = next((v for k, v in EMPLOYMENT if k in (emp_text + " " + tags)), "full_time")
    content = cell(block, "content")
    cat = next((c for c, rx in CATEGORY if re.search(rx, title)), None) or \
        next((c for c, rx in CATEGORY if re.search(rx, content[:200])), "other")
    hw = "ハローワーク" in block or "公共職業安定所" in office
    return {
        "id": "jg-" + jid,
        "status": "open",
        "title_ja": title[:80],
        "employer_ja": employer[:80] if "公開していません" not in employer else "",
        "region": city,
        "category": cat,
        "employment": etype,
        "pay": parse_pay(cell(block, "salary")),
        "hours": parse_hours(cell(block, "hours")),
        "published": published,
        "hellowork_no": jid if hw and re.match(r"^\d{5}-\d{8}$", jid) else "",
        "hellowork_office": office if hw else "",
        "source_url": f"https://www.jobs-go.jp/jobs/detail/{jid}",
    }


def main():
    max_pages = 200
    if "--max-pages" in sys.argv:
        max_pages = int(sys.argv[sys.argv.index("--max-pages") + 1])
    today = datetime.date.today().isoformat()
    jobs, seen = [], set()
    for n in range(1, max_pages + 1):
        try:
            page = fetch(LIST_URL.format(n=n))
        except Exception as e:  # stop on errors, keep what we have
            print(f"page {n}: {e}", file=sys.stderr)
            break
        blocks = page.split('<div class="panel success  job-excerpt">')[1:]
        if not blocks:
            break
        new = 0
        for b in blocks:
            j = parse_block(b)
            if j and j["id"] not in seen:
                seen.add(j["id"])
                j["checked"] = today
                jobs.append(j)
                new += 1
        print(f"page {n}: {len(blocks)} listings, {new} kept", file=sys.stderr)
        if new == 0 and n > 1:
            break
        time.sleep(1)
    if len(jobs) < 20:
        print("Too few listings collected; keeping the old file.", file=sys.stderr)
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "JobsGo, Toyama, 外国人積極採用 (k9)", "collected": today, "jobs": jobs},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"saved {len(jobs)} listings to {OUT.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
