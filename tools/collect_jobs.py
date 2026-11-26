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
    if not employer or "公開していません" in employer:
        return None  # no employer name: excluded (owner instruction 2026-11-26)
    hw = "ハローワーク" in block or "公共職業安定所" in office
    return {
        "id": "jg-" + jid,
        "status": "open",
        "title_ja": title[:80],
        "employer_ja": employer[:80],
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


DETAILS = ROOT / "content/jobs_auto/details.json"
COMPANIES = ROOT / "content/jobs_auto/companies.json"
QUALS = [("license_car", r"普通自動車運転免許|普通自動車免許"), ("license_large", r"大型自動車|中型自動車|準中型"),
         ("care_worker", r"介護福祉士"), ("care_training", r"初任者研修|実務者研修|ヘルパー2級"), ("nurse", r"看護師"),
         ("childcare", r"保育士"), ("cook", r"調理師"), ("welding", r"溶接"), ("forklift", r"フォークリフト"),
         ("crane", r"クレーン|玉掛"), ("electrician", r"電気工事士"), ("pc", r"パソコン|ＰＣ|PCスキル|Excel|エクセル")]
FOREIGN_WORDS = ["外国人", "外国籍", "技能実習", "特定技能", "ベトナム", "インドネシア", "フィリピン", "ネパール", "ミャンマー",
                 "中国人", "ブラジル", "foreign", "Foreign"]


def flat(page):
    page = re.sub(r"(?s)<(script|style).*?</\1>", "", page)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))


def grab(t, rx, n=1):
    m = re.search(rx, t)
    return m.group(n) if m else ""


def parse_detail(page):
    t = flat(page)
    a = t.find("仕事内容")
    end = t.find("この求人に似た")
    t = t[a:end if end > a else a + 8000]
    need = grab(t, r"【必要な免許・資格】(.*?)(?:【|雇用形態)") + " " + grab(t, r"【必要な経験等】(.*?)(?:【|雇用形態)")
    req = " ".join([need, grab(t, r"応募資格(.*?)雇用形態")])
    quals = [k for k, rx in QUALS if re.search(rx, req)]
    body = t[:t.find("会社概要")] if "会社概要" in t else t
    fmention = bool(re.search(r"外国(?!人積極採用)", body))
    jlpt = grab(body, r"(?:日本語能力試験|JLPT)[^N]{0,12}(N[1-5])") or (grab(body, r"(N[1-5])以上") if fmention else "")
    ins = grab(t, r"加入保険等：(\S+)")
    bonus = re.search(r"賞与：あり（前年度実績 年(\d+)回 計 ([\d.]+)ヶ月分）", t)
    d = {
        "quals": quals,
        "age": grab(t, r"【年齢制限、該当事由】\s*(\S+?)(?:、|\s)"),
        "holidays": int(grab(t, r"年間休日数：(\d+)日") or 0) or None,
        "weekly2": grab(t, r"週休二日制：(\S+)"),
        "overtime": int(grab(t, r"時間外労働時間：(\d+)時間") or 0),
        "bonus": float(bonus.group(2)) if bonus else None,
        "raise": "昇給：あり" in t,
        "commute": bool(re.search(r"通勤手当：通勤手当あり", t)),
        "housing": grab(t, r"入居可能住宅：(\S+)"),
        "social_ins": all(x in ins for x in ("健康保険", "厚生年金")),
        "foreign_text": fmention,
        "jlpt": jlpt,
        "employees": int(grab(t, r"企業全体：(\d+)名") or 0) or None,
        "founded": grab(t, r"設立年月日\s*(\d{4})年"),
        "website": grab(t, r"会社ホームページ\s*(https?://[^\s]+)"),
    }
    return d


HW_URL = ("https://www.hellowork.mhlw.go.jp/kensaku/GECA110010.do?screenId=GECA110010&action=dispDetailBtn"
          "&kJNo={no}&kJKbn=1&jGSHNo=&fullPart=1&iNFTeikyoRiyoDtiID=&kSNo=&newArrival=&tatZngy=1&shogaiKbn=0")
SITE_OVERRIDES = ROOT / "content/jobs_auto/site_overrides.json"


def norm_url(u):
    """Clean a homepage URL as typed in a job form (e.g. 'http//www.x.jp', 'www/x.jp'). Returns '' if it is not a URL."""
    u = html.unescape(u or "").strip().replace("：", ":").replace("／", "/")
    scheme = "https://" if re.match(r"(?i)^https", u) else "http://"
    u = re.sub(r"(?i)^h?ttps?[:/]*", "", u).replace("www@", "www.").replace("www/", "www.")
    u = u.lstrip(":/")
    host = u.split("/")[0]
    if "@" in u or "." not in host or " " in host:
        return ""
    return scheme + u


def hellowork_site(no):
    """Read the 'homepage' field of a public Hello Work job listing."""
    req = urllib.request.Request(HW_URL.format(no=no.replace("-", "")), headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=40) as r:
        page = r.read().decode("utf-8", "ignore")
    m = re.search(r'id="ID_hp"[^>]*>(.*?)</', page, re.S)
    return norm_url(text(m.group(1))) if m else ""


def check_company_site(url):
    """Open the company's website, find a recruitment page and look for mentions of foreign staff."""
    out = {"website": url, "ok": False, "recruit_url": "", "foreign_words": [], "title": ""}
    page = ""
    # Try https first (plain http often cannot be reached through our network), then the URL as given.
    for u in dict.fromkeys([re.sub(r"(?i)^http://", "https://", url), url]):
        try:
            page = fetch(u)
            url = u
            break
        except Exception:
            continue
    if not page:
        return out
    out["website"] = url
    out["ok"] = True
    m = re.search(r"<title>(.*?)</title>", page, re.S | re.I)
    out["title"] = html.unescape(m.group(1)).strip()[:80] if m else ""
    from urllib.parse import urljoin
    rec = ""
    for href, label in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        lab = re.sub(r"<[^>]+>", "", label)
        if re.search(r"採用|リクルート|recruit|求人|career", href + lab, re.I) and not href.startswith(("mailto:", "tel:", "javascript")):
            rec = urljoin(url, href)
            break
    texts = [flat(page)]
    if rec:
        out["recruit_url"] = rec
        try:
            texts.append(flat(fetch(rec)))
        except Exception:
            pass
    joined = " ".join(texts)
    out["foreign_words"] = [w for w in FOREIGN_WORDS if w in joined][:5]
    # links on the recruitment page that may be individual job pages
    links = []
    if rec:
        try:
            rp = fetch(rec)
            for href, label in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', rp, re.S | re.I):
                lab = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", label))).strip()
                if 2 <= len(lab) <= 60 and not href.startswith(("mailto:", "tel:", "javascript")):
                    links.append([lab, urljoin(rec, href)])
            # one level deeper: pages that list jobs ("職種から探す", "募集要項", ...)
            from urllib.parse import urlparse
            host = urlparse(rec).netloc
            hubs = [u for lab, u in links if urlparse(u).netloc == host and re.search(r"職種|募集|求人|要項|job|recruit|採用情報|キャリア|中途|新卒", lab + u, re.I)]
            for hub in list(dict.fromkeys(hubs))[:3]:
                try:
                    hp = fetch(hub)
                except Exception:
                    continue
                for href, label in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', hp, re.S | re.I):
                    lab = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", label))).strip()
                    if 2 <= len(lab) <= 60 and not href.startswith(("mailto:", "tel:", "javascript")):
                        links.append([lab, urljoin(hub, href)])
        except Exception:
            pass
    seen, uniq = set(), []
    for lab, u in links:
        if u not in seen and "microsoft.com" not in u and "google.co" not in u:
            seen.add(u)
            uniq.append([lab, u])
    out["links"] = uniq[:200]
    return out


STOP = {"正社員", "募集", "未経験", "歓迎", "スタッフ", "急募", "契約社員", "パート", "アルバイト", "富山", "富山市", "高岡",
        "勤務", "可能", "経験者", "以上", "日勤", "夜勤", "週休", "土日", "休み", "賞与", "年間", "休日", "求人", "採用",
        "株式会社", "店", "店舗", "センター", "業務", "ホーム", "詳細", "こちら", "一覧", "情報", "エントリー", "応募"}


def match_official(title, links):
    toks = [w for w in re.findall(r"[一-龥]{2,}|[ァ-ヴー]{2,}", title) if w not in STOP]
    best, score = "", 0
    for lab, url in links:
        sc = sum(len(w) for w in toks if w in lab)
        if sc > score and sc >= 3:
            best, score = url, sc
    return best


def enrich(jobs, today):
    from concurrent.futures import ThreadPoolExecutor
    details = json.loads(DETAILS.read_text(encoding="utf-8")) if DETAILS.exists() else {}
    todo = [j for j in jobs if j["id"] not in details]
    print(f"detail pages to read: {len(todo)}", file=sys.stderr)
    for i, j in enumerate(todo):
        try:
            details[j["id"]] = parse_detail(fetch(j["source_url"]))
        except Exception as e:
            print(f"detail {j['id']}: {e}", file=sys.stderr)
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}", file=sys.stderr)
            DETAILS.write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
        time.sleep(1)
    keep = {j["id"] for j in jobs}
    details = {k: v for k, v in details.items() if k in keep}
    DETAILS.write_text(json.dumps(details, ensure_ascii=False, indent=0), encoding="utf-8")
    companies = json.loads(COMPANIES.read_text(encoding="utf-8")) if COMPANIES.exists() else {}
    sites = {}
    for j in jobs:
        d = details.get(j["id"], {})
        name = j["employer_ja"]
        c = companies.setdefault(name, {})
        for k in ("employees", "founded", "website"):
            if d.get(k) and not c.get(k):
                c[k] = d[k]
    # Companies whose JobsGo profile has no homepage: use our checked list, then the Hello Work listing (every 30 days).
    overrides = json.loads(SITE_OVERRIDES.read_text(encoding="utf-8")) if SITE_OVERRIDES.exists() else {}
    month_ago = (datetime.date.fromisoformat(today) - datetime.timedelta(days=30)).isoformat()
    for j in jobs:
        c = companies[j["employer_ja"]]
        if c.get("website"):
            continue
        if overrides.get(j["employer_ja"]):
            c["website"], c["website_source"] = overrides[j["employer_ja"]], "search"
        elif j.get("hellowork_no") and c.get("hw_checked", "") < month_ago:
            try:
                url = hellowork_site(j["hellowork_no"])
            except Exception as e:
                print(f"hellowork {j['hellowork_no']}: {e}", file=sys.stderr)
                url = ""
            c["hw_checked"] = today
            if url:
                c["website"], c["website_source"] = url, "hellowork"
            time.sleep(1)
    for j in jobs:
        name = j["employer_ja"]
        c = companies[name]
        if c.get("website") and (not c.get("site_checked") or c["site_checked"] < (datetime.date.fromisoformat(today) - datetime.timedelta(days=30)).isoformat()):
            sites[name] = norm_url(c["website"]) or c["website"]
    print(f"company websites to check: {len(sites)}", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for name, res in zip(sites, ex.map(check_company_site, sites.values())):
            companies[name].update({"site_ok": res["ok"], "site_url": res["website"] if res["ok"] else "", "recruit_url": res["recruit_url"], "links": res.get("links", []),
                                    "site_foreign_words": res["foreign_words"], "site_title": res["title"], "site_checked": today})
    for j in jobs:
        c = companies.get(j["employer_ja"], {})
        j["official_url"] = match_official(j["title_ja"], c.get("links", [])) if c.get("links") else ""
    names = {j["employer_ja"] for j in jobs}
    companies = {k: v for k, v in companies.items() if k in names}
    COMPANIES.write_text(json.dumps(companies, ensure_ascii=False, indent=1), encoding="utf-8")


def sites_only():
    """Re-check company websites and job-page matches without reading JobsGo again."""
    data = json.loads(OUT.read_text(encoding="utf-8"))
    comps = json.loads(COMPANIES.read_text(encoding="utf-8")) if COMPANIES.exists() else {}
    for c in comps.values():
        c.pop("site_checked", None)
    COMPANIES.write_text(json.dumps(comps, ensure_ascii=False), encoding="utf-8")
    enrich(data["jobs"], datetime.date.today().isoformat())
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def new_sites():
    """Look up homepages for companies that have none, and check only sites not checked in the last 30 days."""
    data = json.loads(OUT.read_text(encoding="utf-8"))
    enrich(data["jobs"], datetime.date.today().isoformat())
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    if "--sites-only" in sys.argv:
        return sites_only()
    if "--new-sites" in sys.argv:
        return new_sites()
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
    if "--no-detail" not in sys.argv:
        enrich(jobs, today)
    OUT.write_text(json.dumps({"source": "JobsGo, Toyama, 外国人積極採用 (k9)", "collected": today, "jobs": jobs},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"saved {len(jobs)} listings to {OUT.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
