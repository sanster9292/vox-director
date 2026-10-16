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


def api_key():
    key = os.environ.get("FAL_KEY")
    if key:
        return key
    if sys.platform == "darwin":
        r = subprocess.run(["security", "find-generic-password", "-s", "fal-api-key", "-w"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    sys.exit("No fal API key found. Set FAL_KEY, or on macOS run scripts/set_fal_key.sh "
             "(get a key at https://fal.ai/dashboard/keys).")


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
