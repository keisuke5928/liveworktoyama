#!/usr/bin/env python3
"""Post news articles to Instagram (@liveworktoyama) as Reels.

Instagram reads the video from a public URL, so posting has two steps:

  python3 tools/post_instagram.py --stage [<news-id>]   # make the reel and put it in static/reels/ (newest unposted article)
  (build, commit and merge to main, so the video is live at https://liveworktoyama.com/reels/<id>.mp4)
  python3 tools/post_instagram.py                       # publish every staged reel that is live, then remove it from static/reels/
  python3 tools/post_instagram.py --dry-run             # show what would happen

The token is never stored here: in the Claude cloud session the network proxy adds the Page token
to requests to graph.facebook.com. Posted reels are recorded in content/social/instagram.json.
The removal of the posted video from static/reels/ goes out with the next commit.
"""
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / "content/news"
REELS = ROOT / "_reels"
STAGE = ROOT / "static/reels"
LOG = ROOT / "content/social/instagram.json"
API = "https://graph.facebook.com/v27.0"
SITE = "https://liveworktoyama.com"
IG_USER = "17841466716525932"  # @liveworktoyama
HDR = {"Authorization": "Bearer placeholder"}  # the real token is added by the network proxy


def call(path, data=None, method="GET"):
    url = f"{API}/{path}"
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        method = "POST"
    req = urllib.request.Request(url, data=body, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Graph API error {e.code}: {e.read().decode()[:400]}")


def load_log():
    return json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}


def make(news_id):
    mp4, txt = REELS / f"{news_id}.mp4", REELS / f"{news_id}.txt"
    if not (mp4.exists() and txt.exists()):
        subprocess.run(["node", str(ROOT / "tools/make_reel.mjs"), news_id], check=True)
    return mp4, txt


def stage(args):
    log = load_log()
    if not args and STAGE.exists() and any(STAGE.glob("*.mp4")):  # keep one reel a day: something is already waiting
        print("a reel is already staged:", ", ".join(f.name for f in STAGE.glob("*.mp4")))
        return
    ids = args or [d.name for d in sorted(NEWS.iterdir(), reverse=True) if (d / "meta.json").exists() and d.name not in log][:1]
    if not ids:
        print("nothing new to stage")
        return
    STAGE.mkdir(parents=True, exist_ok=True)
    for news_id in ids:
        mp4, _ = make(news_id)
        shutil.copy(mp4, STAGE / f"{news_id}.mp4")
        print(f"staged static/reels/{news_id}.mp4 ({mp4.stat().st_size / 1e6:.1f} MB). Build, commit and merge, then run without --stage.")


def live(url, size):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200 and int(r.headers.get("Content-Length") or size) == size
    except Exception:
        return False


def publish(dry):
    log = load_log()
    staged = sorted(STAGE.glob("*.mp4")) if STAGE.exists() else []
    if not staged:
        print("no staged reels")
        return
    for f in staged:
        news_id = f.stem
        if news_id in log:
            f.unlink()
            continue
        url = f"{SITE}/reels/{f.name}"
        if not live(url, f.stat().st_size):
            print(f"{news_id}: not live yet at {url} (merge to main and wait for the deploy)")
            continue
        _, txt = make(news_id)
        caption = txt.read_text(encoding="utf-8").strip()
        if dry:
            print(f"--- would post {news_id} from {url}\n{caption}\n")
            continue
        c = call(f"{IG_USER}/media", {"media_type": "REELS", "video_url": url, "caption": caption, "share_to_feed": "true"})
        cid = c["id"]
        for _ in range(60):  # Instagram downloads and processes the video
            st = call(f"{cid}?fields=status_code,status")
            if st.get("status_code") == "FINISHED":
                break
            if st.get("status_code") in ("ERROR", "EXPIRED"):
                raise SystemExit(f"{news_id}: Instagram could not process the video: {st}")
            time.sleep(10)
        else:
            raise SystemExit(f"{news_id}: processing took too long; try again later")
        res = call(f"{IG_USER}/media_publish", {"creation_id": cid})
        log[news_id] = res.get("id")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        f.unlink()
        print(f"posted {news_id}: {res.get('id')} (removed static/reels/{f.name}; commit the removal)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--stage" in sys.argv:
        stage(args)
    else:
        publish("--dry-run" in sys.argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
