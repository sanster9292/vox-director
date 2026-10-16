#!/usr/bin/env python3
"""Project layout + state helpers shared by the stage scripts.

<project>/
  beats.json      the plan (you write this; see SKILL.md for the schema)
  state.json      output URLs the scripts record (keyframe URLs feed the video stage)
  keyframes/  clips/  audio/  captions/  references/  review/
  logs/           every request payload + fal result, one JSON per job
  draft/          the same layout for a cheap ideation pass (--draft); beats.json and references/
                  are links to the project's own, and beats.json "draft" overrides apply there
"""
import argparse
import json
import os

DIRS = ("keyframes", "clips", "audio", "captions", "references", "review", "logs")


def args(desc, extra=None):
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("project", help="project directory containing beats.json")
    p.add_argument("--ids", help="comma-separated beat ids to (re)do, e.g. 1,4")
    p.add_argument("--dry-run", action="store_true", help="print jobs + cost estimate, submit nothing")
    p.add_argument("--draft", action="store_true",
                   help="cheap ideation pass: work in <project>/draft with the beats.json \"draft\" overrides")
    if extra:
        extra(p)
    a = p.parse_args()
    a.ids = {int(x) for x in a.ids.split(",")} if a.ids else None
    if a.draft and not is_draft(a.project):
        a.project = make_draft(a.project)
    a.draft = is_draft(a.project)
    for d in DIRS:
        os.makedirs(os.path.join(a.project, d), exist_ok=True)
    return a


# What a draft pass changes when beats.json has no "draft" block: lowest-cost video tier and no 2K
# pass. Put cheaper models in beats.json "draft" too (e.g. "draft": {"image": {"model": ...}}).
DRAFT_DEFAULTS = {"video": {"params": {"resolution": "480P"}}}


def is_draft(project):
    return os.path.basename(os.path.normpath(project)) == "draft"


def make_draft(project):
    """<project>/draft with links back to the project's beats.json and references/."""
    d = os.path.join(project, "draft")
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(project, "references"), exist_ok=True)
    for name in ("beats.json", "references"):
        link = os.path.join(d, name)
        if not os.path.lexists(link):
            os.symlink(os.path.join("..", name), link)
    return d


def _merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(project):
    doc = json.load(open(os.path.join(project, "beats.json")))
    if is_draft(project):
        doc = _merge(doc, doc.get("draft") or DRAFT_DEFAULTS)
    return doc


def save_doc(project, doc):
    json.dump(doc, open(os.path.join(project, "beats.json"), "w"), indent=1, ensure_ascii=False)


def state(project):
    p = os.path.join(project, "state.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def save_state(project, st):
    json.dump(st, open(os.path.join(project, "state.json"), "w"), indent=1)


def log(project, name, payload, result):
    json.dump({"input": payload, "result": result},
              open(os.path.join(project, "logs", f"{name}.json"), "w"), indent=1, ensure_ascii=False)


def keep_previous(path):
    """Move an existing output aside as <name>_takeN.<ext> so re-rolls never destroy a take."""
    if not os.path.exists(path):
        return
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{base}_take{n}{ext}"):
        n += 1
    os.rename(path, f"{base}_take{n}{ext}")


def need(doc, section, key="model"):
    """A model the project must name in beats.json. Nothing is defaulted: models are chosen per
    project at the approval gate (open weights first; see references/fal-models.md)."""
    val = (doc.get(section) or {}).get(key)
    if not val:
        raise SystemExit(f'beats.json is missing "{section}.{key}". Pick a model at the approval gate '
                         f"(open weights first; candidates in references/fal-models.md) and add it.")
    return val


def selected(doc, ids):
    return [b for b in doc["beats"] if not ids or b["id"] in ids]
