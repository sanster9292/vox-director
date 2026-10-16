#!/usr/bin/env python3
"""Find and fetch real reference photos of landmarks from Wikimedia Commons (freely licensed).

  python3 scripts/refs.py search "Clock Tower Faisalabad" [--limit 8]
  python3 scripts/refs.py get <project> <name.jpg> "<File:Title.jpg or thumb URL>"
  python3 scripts/refs.py sheet <project>          # contact sheet of references/ for review

Why Commons and not Google Images: results can be fetched by script without scraping, and every
file states its licence and author. `get` writes references/CREDITS.md so the creator can credit
the photographers (CC BY / CC BY-SA require attribution if the video is published).
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

import falq  # only for its SSL context

UA = "vox-director-fal/1.0 (reference photo lookup)"
API = "https://commons.wikimedia.org/w/api.php"


def query(params):
    url = API + "?" + urllib.parse.urlencode(dict(params, format="json"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30, context=falq._CTX) as r:
        return json.load(r)


def info(pages):
    out = []
    for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        ii = p["imageinfo"][0]
        m = ii.get("extmetadata", {})
        artist = re.sub("<[^>]+>", "", m.get("Artist", {}).get("value", "")).strip()
        out.append(dict(title=p["title"], width=ii["width"], height=ii["height"],
                        license=m.get("LicenseShortName", {}).get("value", "?"), artist=artist,
                        url=ii.get("thumburl") or ii["url"], page=ii.get("descriptionurl", "")))
    return out


IIPROP = {"prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1280}


def search(q, limit=8):
    d = query(dict(IIPROP, action="query", generator="search", gsrnamespace=6, gsrsearch=q, gsrlimit=limit))
    for i in info(d.get("query", {}).get("pages", {})):
        print(f"{i['title']}\n    {i['width']}x{i['height']}  {i['license']}  by {i['artist'][:40]}\n    {i['url']}")


def get(project, name, src):
    title = src if src.startswith("File:") else None
    if not title:  # derive the File: title from a thumb/upload URL
        fn = urllib.parse.unquote(src.split("?")[0].rstrip("/").split("/")[-1])
        fn = re.sub(r"^\d+px-", "", fn)
        title = "File:" + fn
    d = query(dict(IIPROP, action="query", titles=title))
    i = info(d["query"]["pages"])[0]
    dest_dir = os.path.join(project, "references")
    os.makedirs(dest_dir, exist_ok=True)
    subprocess.run(["curl", "-s", "-L", "-A", UA, "-o", os.path.join(dest_dir, name), i["url"]], check=True)
    with open(os.path.join(dest_dir, "CREDITS.md"), "a") as f:
        f.write(f"- `{name}`: \"{i['title'][5:]}\" by {i['artist'] or 'unknown'}, {i['license']}, {i['page']}\n")
    print(f"saved references/{name}  ({i['license']}, by {i['artist'][:40]})")


def sheet(project):
    ref = os.path.join(project, "references")
    files = sorted(f for f in os.listdir(ref) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
    if not files:
        sys.exit("no reference photos yet")
    args = ["ffmpeg", "-v", "error", "-y"]
    for f in files:
        args += ["-i", os.path.join(ref, f)]
    chain = "".join(f"[{i}]scale=-2:300[s{i}];" for i in range(len(files)))
    chain += "".join(f"[s{i}]" for i in range(len(files))) + f"hstack={len(files)}" if len(files) > 1 else "[s0]null"
    out = os.path.join(project, "review", "references_sheet.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(args + ["-filter_complex", chain, out], check=True)
    print(out, "  (left to right:", ", ".join(files) + ")")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "search":
        lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 8
        search(sys.argv[2], lim)
    elif cmd == "get":
        get(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "sheet":
        sheet(sys.argv[2])
    else:
        sys.exit(__doc__)
