#!/usr/bin/env python3
"""Find and save free photos (Wikimedia Commons) for articles and guides, with credits.

  python3 tools/fetch_photo.py search "Kansui Park Toyama"            # list candidates with license and author
  python3 tools/fetch_photo.py get "File:Some photo.jpg" kansui-park   # save static/img/photos/kansui-park.jpg

Only licenses that allow commercial use are accepted: CC0, public domain, CC BY, CC BY-SA.
The photo is cropped to 1200x630 (same shape as the article cards), saved as a small JPEG
without camera data, and its author, license and source are written to content/photos.json.
build.py shows the credit under the photo. Use it in a news meta.json as "photo": "<slug>".
"""
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static/img/photos"
CREDITS = ROOT / "content/photos.json"
API = "https://commons.wikimedia.org/w/api.php"
UA = "LiveWorkToyamaBot/1.0 (https://liveworktoyama.com/about/)"  # Wikimedia asks for a descriptive User-Agent
OK = re.compile(r"^(CC0|Public domain|PD.*|CC BY(-SA)? \d(\.\d)?.*)$", re.I)


def api(**params):
    params.update(format="json")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    for wait in (5, 15, 45, 90, 0):  # Wikimedia rate limits busy clients (HTTP 429): wait and try again
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code != 429 or not wait:
                raise
            time.sleep(int(e.headers.get("Retry-After") or wait))


def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def info(titles, width=1280):  # Wikimedia asks clients to use its standard thumbnail sizes
    d = api(action="query", prop="imageinfo", titles=titles, iiprop="url|extmetadata|size|mime", iiurlwidth=width)
    out = []
    for p in d["query"]["pages"].values():
        if "imageinfo" not in p:
            continue
        ii = p["imageinfo"][0]
        m = ii.get("extmetadata", {})
        out.append({
            "file": p["title"],
            "license": m.get("LicenseShortName", {}).get("value", ""),
            "license_url": m.get("LicenseUrl", {}).get("value", ""),
            "author": clean(m.get("Artist", {}).get("value", "")) or "Unknown",
            "date": clean(m.get("DateTimeOriginal", {}).get("value", ""))[:10],
            "desc": clean(m.get("ImageDescription", {}).get("value", ""))[:120],
            "size": f'{ii.get("width")}x{ii.get("height")}',
            "mime": ii.get("mime"),
            "thumb": ii.get("thumburl") or ii.get("url"),
            "source": ii.get("descriptionurl"),
        })
    return out


def search(q):
    d = api(action="query", list="search", srsearch=q, srnamespace=6, srlimit=30)
    titles = [x["title"] for x in d["query"]["search"] if re.search(r"\.(jpe?g|png)$", x["title"], re.I)]
    for i in range(0, len(titles), 20):
        for x in info("|".join(titles[i:i + 20])):
            ok = "OK " if OK.match(x["license"]) else "NO "
            print(f'{ok}{x["file"]} | {x["license"]} | {x["author"][:40]} | {x["size"]} | {x["date"]} | {x["desc"]}')


def get(title, slug):
    x = info(title)[0]
    if not OK.match(x["license"]):
        raise SystemExit(f'license not allowed: {x["license"]}')
    req = urllib.request.Request(x["thumb"], headers={"User-Agent": UA})
    for wait in (10, 30, 90, 0):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                im = Image.open(io.BytesIO(r.read()))
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or not wait:
                raise
            time.sleep(wait)
    im = ImageOps.exif_transpose(im).convert("RGB")
    im = ImageOps.fit(im, (1200, 630), Image.LANCZOS, centering=(0.5, 0.5))
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{slug}.jpg"
    im.save(f, "JPEG", quality=78, optimize=True, progressive=True)  # no EXIF is written
    credits = json.loads(CREDITS.read_text(encoding="utf-8")) if CREDITS.exists() else {}
    credits[slug] = {"src": f"/img/photos/{slug}.jpg", "file": x["file"], "author": x["author"], "license": x["license"],
                     "license_url": x["license_url"], "source": x["source"], "site": "Wikimedia Commons"}
    CREDITS.write_text(json.dumps(credits, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f'saved {f.relative_to(ROOT)} ({f.stat().st_size // 1024} KB) | {x["license"]} | {x["author"]}')


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "search":
        search(" ".join(sys.argv[2:]))
    elif len(sys.argv) == 4 and sys.argv[1] == "get":
        get(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
