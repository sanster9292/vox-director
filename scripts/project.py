#!/usr/bin/env python3
"""Project layout + state helpers shared by the stage scripts.

<project>/
  beats.json      the plan (you write this; see SKILL.md for the schema)
  state.json      output URLs the scripts record (keyframe URLs feed the video stage)
  keyframes/  clips/  audio/  captions/  references/  review/
  logs/           every request payload + fal result, one JSON per job
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
    if extra:
        extra(p)
    a = p.parse_args()
    a.ids = {int(x) for x in a.ids.split(",")} if a.ids else None
    for d in DIRS:
        os.makedirs(os.path.join(a.project, d), exist_ok=True)
    return a


def load(project):
    return json.load(open(os.path.join(project, "beats.json")))


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


def selected(doc, ids):
    return [b for b in doc["beats"] if not ids or b["id"] in ids]
