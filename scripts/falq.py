#!/usr/bin/env python3
"""Shared fal.ai client for vox-director-fal: key lookup, queue submit/poll, parallel batches,
downloads, pricing lookup. Standard library only.

API key lookup order:
  1. FAL_KEY environment variable
  2. macOS Keychain item with service name "fal-api-key" (see scripts/set_fal_key.sh)
"""
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

QUEUE = "https://queue.fal.run"
API = "https://api.fal.ai/v1"


def _ssl_context():
    # python.org builds on macOS often ship without CA certs; fall back to the system bundle.
    try:
        import certifi  # noqa: F401
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


_CTX = _ssl_context()


def secret(env, item, where):
    """An API key from the environment, else the macOS Keychain (scripts/set_key.sh <item>)."""
    key = os.environ.get(env)
    if key:
        return key
    if sys.platform == "darwin":
        r = subprocess.run(["security", "find-generic-password", "-s", item, "-w"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    sys.exit(f"No key found. Set {env}, or on macOS run: zsh scripts/set_key.sh {item}  (get one at {where})")


def api_key():
    return secret("FAL_KEY", "fal-api-key", "https://fal.ai/dashboard/keys")


def _call(url, payload=None, timeout=60):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Key {api_key()}", "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {url}: {e.read().decode(errors='replace')[:600]}") from e


def run(endpoint, payload, label="job", timeout_s=1200):
    """Submit one job to the fal queue and block until it completes; return the result JSON.
    POST is not retried (it creates a billable job); status polls are."""
    job = _call(f"{QUEUE}/{endpoint}", payload)
    print(f"[{label}] submitted {job['request_id']}", file=sys.stderr, flush=True)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(5)
        try:
            st = _call(job["status_url"])
        except RuntimeError as e:
            print(f"[{label}] poll error (will retry): {e}", file=sys.stderr)
            continue
        if st["status"] == "COMPLETED":
            res = _call(job["response_url"])
            print(f"[{label}] done", file=sys.stderr, flush=True)
            return res
    raise RuntimeError(f"[{label}] timed out after {timeout_s}s")


def run_many(jobs, workers=8):
    """jobs: {label: (endpoint, payload)} -> {label: result | Exception}. One failure doesn't stop the batch."""
    def one(item):
        label, (ep, payload) = item
        try:
            return label, run(ep, payload, label)
        except Exception as e:
            print(f"[{label}] FAILED: {e}", file=sys.stderr, flush=True)
            return label, e
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(ex.map(one, jobs.items()))


def first_url(obj):
    """Find the first output URL in a fal result (images[0].url, video.url, audio.url, ...)."""
    if isinstance(obj, dict):
        if isinstance(obj.get("url"), str):
            return obj["url"]
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            u = first_url(v)
            if u:
                return u
    return None


def download(url, dest):
    subprocess.run(["curl", "-s", "-L", "--retry", "3", "-o", dest, url], check=True)
    if not os.path.exists(dest) or os.path.getsize(dest) == 0:
        raise RuntimeError(f"download produced an empty file: {url}")
    return dest


def prices(endpoints):
    """{endpoint: (unit_price, unit)} from fal's pricing API. Returns {} if it can't be reached."""
    q = urllib.parse.urlencode([("endpoint_id", e) for e in sorted(set(endpoints))])
    try:
        d = _call(f"{API}/models/pricing?{q}")
    except Exception as e:
        print(f"(pricing lookup failed: {e})", file=sys.stderr)
        return {}
    return {p["endpoint_id"]: (p["unit_price"], p["unit"]) for p in d.get("prices", [])}


def estimate(jobs, units_fn):
    """Print a per-job cost estimate. units_fn(label, endpoint, payload, unit) -> billable units."""
    table = prices([ep for ep, _ in jobs.values()])
    total = 0.0
    for label, (ep, payload) in jobs.items():
        if ep not in table:
            print(f"  {label:10s} {ep}  (price unknown)")
            continue
        unit_price, unit = table[ep]
        n = units_fn(label, ep, payload, unit)
        total += unit_price * n
        print(f"  {label:10s} {ep}  {n:g} x ${unit_price} per {unit} = ${unit_price * n:.3f}")
    print(f"  estimated total: ${total:.2f}  (list price; promos, resolution tiers and "
          f"per-token billing can make the real charge differ, so check the model page)")
    return total


# ---------------------------------------------------------------- schema-aware payloads
# Models name the same input differently: nano-banana takes aspect_ratio + resolution, Qwen-Image
# and FLUX.2 take image_size; some edit models take image_urls, others image_url; TTS models read
# prompt or text. The stage scripts write one neutral payload and fit() reshapes it to the
# endpoint's own OpenAPI input schema, so switching models is a beats.json change only.
# Unknown fields are dropped with a note instead of being silently ignored by fal.

SCHEMA_URL = "https://fal.ai/api/openapi/queue/openapi.json?endpoint_id={}"
SCHEMA_CACHE = os.path.expanduser("~/.cache/vox-director-fal/schemas")
_schemas, _noted = {}, set()

LONG_SIDE = {"0.5K": 512, "1K": 1024, "2K": 2048, "4K": 4096}
SIZE_ENUM = {"1:1": "square_hd", "4:3": "landscape_4_3", "3:4": "portrait_4_3",
             "16:9": "landscape_16_9", "9:16": "portrait_16_9"}


def _note(endpoint, msg):
    if (endpoint, msg) not in _noted:
        _noted.add((endpoint, msg))
        print(f"  [{endpoint}] {msg}", file=sys.stderr)


def _deref(node, comps):
    while isinstance(node, dict) and "$ref" in node:
        node = comps.get(node["$ref"].split("/")[-1], {})
    return node


def _branches(node, comps):
    """Flatten anyOf/oneOf/allOf/$ref into the list of concrete sub-schemas."""
    node = _deref(node, comps)
    subs = node.get("anyOf") or node.get("oneOf") or node.get("allOf")
    if not subs:
        return [node]
    out = []
    for s in subs:
        out += _branches(s, comps)
    return out


def _enum(node, comps):
    vals = []
    for b in _branches(node, comps):
        vals += b.get("enum", [])
    return vals


def input_schema(endpoint):
    """(properties, components) for an endpoint's input, or None if the schema can't be fetched.
    Cached on disk for a week; no API key needed."""
    if endpoint in _schemas:
        return _schemas[endpoint]
    path = os.path.join(SCHEMA_CACHE, endpoint.replace("/", "__") + ".json")
    spec = None
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * 86400:
        spec = json.load(open(path))
    else:
        try:
            req = urllib.request.Request(SCHEMA_URL.format(urllib.parse.quote(endpoint, safe="/")),
                                         headers={"User-Agent": "vox-director-fal"})
            with urllib.request.urlopen(req, timeout=30, context=_CTX) as r:
                spec = json.load(r)
            os.makedirs(SCHEMA_CACHE, exist_ok=True)
            json.dump(spec, open(path, "w"))
        except Exception as e:
            _note(endpoint, f"schema lookup failed ({e}); sending the payload unchanged")
    result = None
    if spec:
        comps = spec.get("components", {}).get("schemas", {})
        try:
            body = spec["paths"][f"/{endpoint}"]["post"]["requestBody"]["content"]["application/json"]["schema"]
            props = _deref(body, comps).get("properties")
        except (KeyError, TypeError):
            props = next((s.get("properties") for n, s in comps.items()
                          if n.endswith("Input") and s.get("properties")), None)
        if props:
            result = (props, comps)
    _schemas[endpoint] = result
    return result


def _size(aspect, res, node, comps):
    """image_size value: custom {width,height} when the model allows it, else the nearest enum."""
    allows_custom = any(b.get("type") == "object" or "width" in b.get("properties", {})
                        for b in _branches(node, comps))
    w, h = (float(x) for x in aspect.split(":"))
    if allows_custom:
        long_side = LONG_SIDE.get(str(res or "1K").upper(), 1024)
        s = long_side / max(w, h)
        return {"width": int(round(w * s / 16) * 16), "height": int(round(h * s / 16) * 16)}
    enum = _enum(node, comps)
    want = SIZE_ENUM.get(aspect)
    if want in enum:
        return want
    target = w / h
    ratio = {"square_hd": 1, "square": 1, "landscape_4_3": 4 / 3, "portrait_4_3": 3 / 4,
             "landscape_16_9": 16 / 9, "portrait_16_9": 9 / 16}
    cands = [e for e in enum if e in ratio] or [want]
    return min(cands, key=lambda e: abs(ratio.get(e, 1) - target))


def _match_case(value, enum):
    for e in enum:
        if str(e).lower() == str(value).lower():
            return e
    return None


def fit(endpoint, payload):
    """Reshape a neutral payload to this endpoint's input fields. See the block comment above."""
    s = input_schema(endpoint)
    if not s:
        return payload
    props, comps = s
    p = dict(payload)

    # reference images: image_urls <-> image_url
    if "image_urls" in p and "image_urls" not in props:
        urls = p.pop("image_urls")
        alt = next((k for k in ("image_url", "input_image_url", "image") if k in props), None)
        if alt and urls:
            p[alt] = urls[0]
            if len(urls) > 1:
                _note(endpoint, f"takes one reference image; using the first of {len(urls)}")
    if "image_url" in p and "image_url" not in props and "image_urls" in props:
        p["image_urls"] = [p.pop("image_url")]

    # text: prompt <-> text <-> input
    for k in ("prompt", "text"):
        if k in p and k not in props:
            alt = next((a for a in ("prompt", "text", "input", "gen_text") if a in props and a not in p), None)
            if alt:
                p[alt] = p.pop(k)

    # framing: aspect_ratio + resolution  ->  image_size, when that's what the model takes
    aspect, res = p.get("aspect_ratio"), p.get("resolution")
    if aspect and "aspect_ratio" not in props and "image_size" in props and "image_size" not in p:
        p["image_size"] = _size(aspect, res, props["image_size"], comps)
        for k in ("aspect_ratio", "resolution"):  # folded into image_size
            if k not in props:
                p.pop(k, None)
    for k in ("aspect_ratio", "resolution"):
        if k in p and k in props:
            enum = _enum(props[k], comps)
            if enum:
                hit = _match_case(p[k], enum)
                if hit is None:
                    _note(endpoint, f"{k}={p[k]!r} not offered (choices: {enum}); leaving it to the model default")
                    del p[k]
                else:
                    p[k] = hit

    # duration: snap to the model's enum / range (shorter shots get trimmed in assembly)
    if "duration" in p and "duration" in props:
        node, want = props["duration"], float(p["duration"])
        enum = _enum(node, comps)
        if enum:
            nums = sorted(enum, key=lambda e: float(str(e).rstrip("s")))
            pick = next((e for e in nums if float(str(e).rstrip("s")) >= want), nums[-1])
            if float(str(pick).rstrip("s")) != want:
                _note(endpoint, f"duration {want:g}s not offered; using {pick}")
            p["duration"] = pick
        else:
            b = next((b for b in _branches(node, comps) if "minimum" in b or "maximum" in b), {})
            v = min(max(want, b.get("minimum", want)), b.get("maximum", want))
            if v != want:
                _note(endpoint, f"duration {want:g}s outside the model's range; using {v:g}")
            types = {b.get("type") for b in _branches(node, comps)}
            p["duration"] = str(int(v)) if types == {"string"} else (int(v) if v == int(v) else v)

    dropped = [k for k in p if k not in props]
    for k in dropped:
        del p[k]
    if dropped:
        _note(endpoint, f"not an input of this model, dropped: {', '.join(dropped)}")
    return p
