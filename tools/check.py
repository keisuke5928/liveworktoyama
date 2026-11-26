#!/usr/bin/env python3
"""Check the built site in _site/ before publishing.

Usage: python3 build.py && python3 tools/check.py
Fails (exit 1) on: broken internal links or images, invalid JSON-LD,
hreflang pairs that do not point back, pages without title/description,
news articles missing a language file or a required section.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"
LANGS = json.loads((ROOT / "content/site.json").read_text())["langs"]
problems = []

pages = {f: f.read_text(encoding="utf-8") for f in SITE.rglob("*.html")}
alt = {}
for f, s in pages.items():
    rel = f.relative_to(SITE)
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
        try:
            json.loads(m)
        except ValueError as e:
            problems.append(f"{rel}: invalid JSON-LD ({e})")
    for h in re.findall(r'(?:href|src)="(/[^"#?]*)', s):
        t = SITE / h.lstrip("/")
        if not (t.is_file() or (t / "index.html").is_file()):
            problems.append(f"{rel}: broken link {h}")
    if rel.name != "404.html":
        if not re.search(r"<title>[^<]+</title>", s):
            problems.append(f"{rel}: no <title>")
        if not re.search(r'<meta name="description" content="[^"]+">', s):
            problems.append(f"{rel}: no meta description")
    can = re.search(r'rel="canonical" href="([^"]+)"', s)
    if can:
        alt[can.group(1)] = set(re.findall(r'hreflang="[^"]+" href="([^"]+)"', s))
for u, a in alt.items():
    for v in a:
        if v in alt and alt[v] and u not in alt[v]:
            problems.append(f"hreflang not reciprocal: {u} -> {v}")

for d in sorted((ROOT / "content/news").iterdir()):
    if not d.is_dir():
        continue
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    for key in ("date", "category", "region", "image", "sources", "easy_summary"):
        if not meta.get(key):
            problems.append(f"news/{d.name}: meta.json missing '{key}'")
    if meta.get("image") and not (ROOT / "static" / meta["image"].lstrip("/")).is_file():
        problems.append(f"news/{d.name}: image not found (run node tools/make-images.mjs)")
    for lang in LANGS:
        f = d / f"{lang}.md"
        if not f.exists():
            problems.append(f"news/{d.name}: missing {lang}.md")
            continue
        text = f.read_text(encoding="utf-8")
        for need in ("title:", "description:", "+++ short", "+++ body", "+++ meaning"):
            if need not in text:
                problems.append(f"news/{d.name}/{lang}.md: missing '{need}'")

# job listings (CLAUDE.md chapter 6)
JOB_BOARDS = ("indeed.", "townwork", "baitoru", "mynavi", "rikunabi", "doda", "en-japan", "hellowork.mhlw.go.jp",
              "jobmedley", "stanby", "kyujinbox", "careerjet", "glassdoor", "linkedin.com/jobs", "jobs.yahoo", "airwork",
              "engage", "hatarako", "an-", "gaijinpot", "jobs-in-japan", "workport")
UI = json.loads((ROOT / "content/ui.json").read_text(encoding="utf-8"))
REQ = ("status", "title", "employer", "region", "category", "employment", "source_url", "source_name",
       "foreign_welcome", "checked", "first_listed")
import datetime
for f in sorted((ROOT / "content/jobs").glob("*.json")) if (ROOT / "content/jobs").exists() else []:
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        problems.append(f"jobs/{f.name}: invalid JSON ({e})"); continue
    for k in REQ:
        if not j.get(k):
            problems.append(f"jobs/{f.name}: missing '{k}'")
    if j.get("status") not in ("open", "closed"):
        problems.append(f"jobs/{f.name}: status must be open or closed")
    url = (j.get("source_url") or "").lower()
    if not url.startswith("https://") and not url.startswith("http://"):
        problems.append(f"jobs/{f.name}: source_url must be a full URL")
    if any(b in url for b in JOB_BOARDS):
        problems.append(f"jobs/{f.name}: source must be the employer's own page or a public body, not a job board ({url})")
    for k in ("checked", "first_listed"):
        try:
            datetime.date.fromisoformat(j.get(k, ""))
        except ValueError:
            problems.append(f"jobs/{f.name}: '{k}' must be YYYY-MM-DD")
    for k, pre in (("region", "region_"), ("category", "job_cat_"), ("employment", "emp_"), ("japanese", "jp_"), ("housing", "housing_")):
        if j.get(k) and pre + j[k] not in UI["en"]:
            problems.append(f"jobs/{f.name}: unknown {k} '{j[k]}' (add {pre}{j[k]} to ui.json)")
    if isinstance(j.get("title"), dict):
        for lang in LANGS:
            if not j["title"].get(lang) and lang not in ("easy",):
                problems.append(f"jobs/{f.name}: title missing for {lang}")
    if j.get("pay") and j["pay"].get("per") not in ("month", "hour", "year", "day"):
        problems.append(f"jobs/{f.name}: pay.per must be month/hour/year/day")

if problems:
    print("\n".join(problems))
    print(f"\nFAILED: {len(problems)} problem(s)")
    sys.exit(1)
print(f"OK: {len(pages)} pages checked")
