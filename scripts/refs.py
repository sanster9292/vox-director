#!/usr/bin/env python3
"""Reference photos of real places, so the image model draws the real building, street or shop
instead of inventing one.

Order of preference (SKILL.md step 2):
  1. The person's own photos      refs.py add <project> <name.jpg> <path/to/photo> [--credit "..."]
  2. Web search, ONLY after the person says yes to searching:
       google   Google Maps place photos (best for restaurants, shops, venues; needs a key)
       pexels   Pexels stock photos (high quality, free licence; needs a free key)
       geo      Wikimedia Commons photos geotagged near the place (no key)
       commons  Wikimedia Commons keyword search (no key)

  python3 scripts/refs.py search "Lyallpur Clock Tower Faisalabad" [--source google|pexels|geo|commons|all] [--limit 6]
  python3 scripts/refs.py get <project> <name.jpg> <id from search>
  python3 scripts/refs.py add <project> <name.jpg> <local photo> [--credit "photo by ..."]
  python3 scripts/refs.py sheet <project>          # contact sheet of references/ to look at

`search` prints an id per result (File:..., pexels:123, google:places/.../photos/..., or a URL);
pass it to `get`. Every saved photo gets a line in references/CREDITS.md with its source, author
and licence, so the person can credit photographers when they publish.

People are never searched for: photos of a real person come from the person asking (with the
consent of whoever is pictured). Keys: env PEXELS_API_KEY / GOOGLE_MAPS_API_KEY, or on macOS the
Keychain items "pexels-api-key" / "google-maps-api-key" (zsh scripts/set_key.sh <item>).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

import falq  # SSL context + key lookup

UA = "vox-director-fal/1.1 (reference photo lookup)"
COMMONS = "https://commons.wikimedia.org/w/api.php"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
PEXELS = "https://api.pexels.com/v1"
PLACES = "https://places.googleapis.com/v1"


def http_json(url, headers=None, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"User-Agent": UA, **(headers or {}),
                                          **({"Content-Type": "application/json"} if data is not None else {})},
                                 method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=30, context=falq._CTX) as r:
        return json.load(r)


def fetch(url, dest, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60, context=falq._CTX) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    if os.path.getsize(dest) == 0:
        raise RuntimeError(f"empty download: {url}")


def credit(project, line):
    with open(os.path.join(project, "references", "CREDITS.md"), "a") as f:
        f.write(f"- {line}\n")


# ---------------------------------------------------------------- Wikimedia Commons

IIPROP = {"prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1600}


def _commons(params):
    return http_json(COMMONS + "?" + urllib.parse.urlencode(dict(params, format="json")))


def _commons_info(pages):
    out = []
    for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        if "imageinfo" not in p:
            continue
        ii = p["imageinfo"][0]
        m = ii.get("extmetadata", {})
        artist = re.sub("<[^>]+>", "", m.get("Artist", {}).get("value", "")).strip()
        out.append(dict(id=p["title"], w=ii["width"], h=ii["height"], author=artist,
                        license=m.get("LicenseShortName", {}).get("value", "?"),
                        url=ii.get("thumburl") or ii["url"], page=ii.get("descriptionurl", "")))
    return out


def search_commons(q, limit):
    d = _commons(dict(IIPROP, action="query", generator="search", gsrnamespace=6, gsrsearch=q, gsrlimit=limit))
    return _commons_info(d.get("query", {}).get("pages", {}))


def search_geo(q, limit, radius_m=400):
    """Photos geotagged within radius_m of the place: geocode the name (OpenStreetMap), then ask
    Commons for files taken near those coordinates."""
    hits = http_json(NOMINATIM + "?" + urllib.parse.urlencode({"q": q, "format": "json", "limit": 1}))
    if not hits:
        print(f"  geo: OpenStreetMap doesn't know '{q}'; try a fuller name with the city", file=sys.stderr)
        return []
    lat, lon = hits[0]["lat"], hits[0]["lon"]
    print(f"  geo: {hits[0].get('display_name', q)[:90]}  ({lat}, {lon})", file=sys.stderr)
    d = _commons(dict(IIPROP, action="query", generator="geosearch", ggsnamespace=6,
                      ggscoord=f"{lat}|{lon}", ggsradius=radius_m, ggslimit=limit))
    return _commons_info(d.get("query", {}).get("pages", {}))


def get_commons(project, name, title):
    if not title.startswith("File:"):  # a thumb/upload URL -> File: title
        fn = urllib.parse.unquote(title.split("?")[0].rstrip("/").split("/")[-1])
        title = "File:" + re.sub(r"^\d+px-", "", fn)
    i = _commons_info(_commons(dict(IIPROP, action="query", titles=title))["query"]["pages"])[0]
    fetch(i["url"], os.path.join(project, "references", name))
    credit(project, f'`{name}`: Wikimedia Commons "{i["id"][5:]}" by {i["author"] or "unknown"}, '
                    f'{i["license"]}, {i["page"]}')
    return i["license"]


# ---------------------------------------------------------------- Pexels

def search_pexels(q, limit):
    key = falq.secret("PEXELS_API_KEY", "pexels-api-key", "https://www.pexels.com/api/")
    d = http_json(f"{PEXELS}/search?" + urllib.parse.urlencode({"query": q, "per_page": limit}),
                  headers={"Authorization": key})
    return [dict(id=f"pexels:{p['id']}", w=p["width"], h=p["height"], author=p.get("photographer", ""),
                 license="Pexels License", url=p["src"]["large2x"], page=p["url"], alt=p.get("alt", ""))
            for p in d.get("photos", [])]


def get_pexels(project, name, pid):
    key = falq.secret("PEXELS_API_KEY", "pexels-api-key", "https://www.pexels.com/api/")
    p = http_json(f"{PEXELS}/photos/{pid}", headers={"Authorization": key})
    fetch(p["src"]["large2x"], os.path.join(project, "references", name))
    credit(project, f'`{name}`: Pexels photo by {p.get("photographer", "unknown")}, Pexels License, {p["url"]}')
    return "Pexels License"


# ---------------------------------------------------------------- Google Maps place photos

def _gkey():
    return falq.secret("GOOGLE_MAPS_API_KEY", "google-maps-api-key",
                       "https://console.cloud.google.com/google/maps-apis (enable Places API (New))")


def search_google(q, limit):
    d = http_json(f"{PLACES}/places:searchText", data={"textQuery": q, "pageSize": 1},
                  headers={"X-Goog-Api-Key": _gkey(),
                           "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.photos"})
    places = d.get("places", [])
    if not places:
        return []
    pl = places[0]
    print(f"  google: {pl['displayName']['text']}, {pl.get('formattedAddress', '')}", file=sys.stderr)
    out = []
    for ph in pl.get("photos", [])[:limit]:
        who = ", ".join(a.get("displayName", "") for a in ph.get("authorAttributions", []))
        out.append(dict(id=f"google:{ph['name']}", w=ph.get("widthPx", 0), h=ph.get("heightPx", 0),
                        author=who, license="Google Maps photo (see note)", url="", page=""))
    return out


def get_google(project, name, photo_name):
    d = http_json(f"{PLACES}/{photo_name}/media?" + urllib.parse.urlencode(
        {"maxWidthPx": 1600, "skipHttpRedirect": "true", "key": _gkey()}))
    fetch(d["photoUri"], os.path.join(project, "references", name))
    credit(project, f"`{name}`: Google Maps place photo ({photo_name.split('/photos/')[0]}). "
                    f"Use as a reference only; check Google Maps terms before showing it unaltered.")
    return "Google Maps photo"


# ---------------------------------------------------------------- commands

SOURCES = {"google": search_google, "pexels": search_pexels, "geo": search_geo, "commons": search_commons}


def cmd_search(q, source, limit):
    for src in (["google", "pexels", "geo", "commons"] if source == "all" else [source]):
        try:
            results = SOURCES[src](q, limit)
        except SystemExit as e:  # missing key: say so, carry on with the next source
            print(f"[{src}] skipped: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"[{src}] failed: {e}", file=sys.stderr)
            continue
        print(f"[{src}] {len(results)} result(s)")
        for r in results:
            alt = f"  \"{r['alt'][:60]}\"" if r.get("alt") else ""
            print(f"  {r['id']}\n      {r['w']}x{r['h']}  {r['license']}  by {r['author'][:40]}{alt}")


def cmd_get(project, name, src):
    os.makedirs(os.path.join(project, "references"), exist_ok=True)
    if src.startswith("pexels:"):
        lic = get_pexels(project, name, src.split(":", 1)[1])
    elif src.startswith("google:"):
        lic = get_google(project, name, src.split(":", 1)[1])
    elif src.startswith("File:") or "wikimedia.org" in src:
        lic = get_commons(project, name, src)
    elif src.startswith("http"):
        fetch(src, os.path.join(project, "references", name))
        credit(project, f"`{name}`: {src} (licence unknown: check before publishing)")
        lic = "unknown"
    else:
        sys.exit(f"don't know how to fetch {src!r}; use an id printed by `search`, or a URL")
    print(f"saved references/{name}  ({lic})")


def cmd_add(project, name, path, who):
    os.makedirs(os.path.join(project, "references"), exist_ok=True)
    shutil.copyfile(os.path.expanduser(path), os.path.join(project, "references", name))
    credit(project, f"`{name}`: supplied by the person ({who or 'their own photo'})")
    print(f"saved references/{name}")


def cmd_sheet(project):
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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("search")
    s.add_argument("query")
    s.add_argument("--source", default="all", choices=["all", *SOURCES])
    s.add_argument("--limit", type=int, default=6)
    g = sp.add_parser("get")
    g.add_argument("project"); g.add_argument("name"); g.add_argument("src")
    d = sp.add_parser("add")
    d.add_argument("project"); d.add_argument("name"); d.add_argument("path")
    d.add_argument("--credit", default="")
    h = sp.add_parser("sheet")
    h.add_argument("project")
    a = ap.parse_args()
    if a.cmd == "search":
        cmd_search(a.query, a.source, a.limit)
    elif a.cmd == "get":
        cmd_get(a.project, a.name, a.src)
    elif a.cmd == "add":
        cmd_add(a.project, a.name, a.path, a.credit)
    else:
        cmd_sheet(a.project)
