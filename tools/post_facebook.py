#!/usr/bin/env python3
"""Post new news articles to the Facebook Page (https://www.facebook.com/liveworktoyama).

  python3 tools/post_facebook.py            # post articles not posted yet (newest first, max 2)
  python3 tools/post_facebook.py --dry-run  # show what would be posted
  python3 tools/post_facebook.py <news-id>  # post one article

Uses the Graph API with a Page access token. The token is never stored in this repository:
in the Claude cloud session the network proxy adds it to requests to graph.facebook.com.
Posted articles are recorded in content/social/facebook.json so nothing is posted twice.
Run only after the article is live on the site (the link preview is read from the page).
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / "content/news"
LOG = ROOT / "content/social/facebook.json"
API = "https://graph.facebook.com/v21.0"
SITE = "https://liveworktoyama.com"


def read_doc(path):
    raw = path.read_text(encoding="utf-8")
    head, rest = raw.split("\n---\n", 1)
    fm = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    sec = {}
    for part in rest.split("\n+++ ")[1:] if not rest.startswith("+++ ") else ("\n" + rest).split("\n+++ ")[1:]:
        name, _, body = part.partition("\n")
        sec[name.strip()] = body.strip()
    fm["points"] = [l.split(". ", 1)[-1].strip() for l in sec.get("short", "").splitlines() if l.strip()]
    return fm


def message(news_id):
    d = NEWS / news_id
    en = read_doc(d / "en.md")
    other = {l: read_doc(d / f"{l}.md") for l in ("vi", "id", "easy") if (d / f"{l}.md").exists()}
    lines = [en["title"], ""] + [f"✅ {p}" for p in en["points"][:3]] + [""]
    flags = {"vi": "🇻🇳", "id": "🇮🇩", "easy": "🇯🇵"}
    for l, doc in other.items():
        lines.append(f"{flags[l]} {doc['title']}")
    lines += ["", "5 languages / 5 ngôn ngữ / 5 bahasa / 5つの ことば:",
              f"{SITE}/en/news/{news_id}/", "",
              "Private information site, not a public office. For your own visa, ask immigration or a gyoseishoshi.", "",
              "#Toyama #富山 #LiveInJapan #WorkInJapan #NguoiVietTaiNhat #OrangIndonesiaDiJepang"]
    return "\n".join(lines)


def post(news_id, dry):
    msg = message(news_id)
    link = f"{SITE}/en/news/{news_id}/"
    if dry:
        print(f"--- {news_id}\n{msg}\n")
        return None
    data = urllib.parse.urlencode({"message": msg, "link": link}).encode()
    # The real token is added by the network proxy; this placeholder is replaced.
    req = urllib.request.Request(f"{API}/me/feed", data=data, headers={"Authorization": "Bearer placeholder"})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.loads(r.read().decode())
    print(f"posted {news_id}: {res.get('id')}")
    return res.get("id")


def main():
    dry = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    ids = args or [d.name for d in sorted(NEWS.iterdir(), reverse=True) if (d / "meta.json").exists() and d.name not in log][:2]
    if not ids:
        print("nothing new to post")
        return 0
    for news_id in reversed(ids):  # older first, so the newest ends up on top
        if news_id in log and not args:
            continue
        pid = post(news_id, dry)
        if pid:
            log[news_id] = pid
            LOG.parent.mkdir(parents=True, exist_ok=True)
            LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
