#!/usr/bin/env python3
"""Stage 3: one narration file per beat (so each line lands on its own cut) plus a music bed.

TTS and music models are set in beats.json "tts" / "music". Field names differ by model
(Gemini TTS reads "prompt", xAI TTS reads "text"), so "tts.text_field" says where the line goes.

  python3 scripts/audio.py <project> [--ids 2] [--only tts|music] [--dry-run]
"""
import os
import sys

import falq
import project as P

a = P.args("Narration + music",
           lambda p: p.add_argument("--only", choices=["tts", "music"], help="do just one of the two"))
doc = P.load(a.project)
tts = doc.get("tts", {})
TTS_MODEL = tts.get("model", "google/gemini-3.8-flash-tts")
TEXT_FIELD = tts.get("text_field", "prompt")
TTS_PARAMS = tts.get("params", {"voice": "Charon"})
music = doc.get("music", {})
MUSIC_MODEL = music.get("model", "fal-ai/minimax-music/v2.6")

jobs = {}
if a.only != "music":
    for b in P.selected(doc, a.ids):
        if b.get("narration"):
            jobs[f"vo{b['id']}"] = (TTS_MODEL, dict({TEXT_FIELD: b["narration"]}, **TTS_PARAMS))
if a.only != "tts" and not a.ids and music.get("prompt"):
    jobs["music"] = (MUSIC_MODEL, dict({"prompt": music["prompt"], "is_instrumental": True},
                                       **music.get("params", {})))


def units(label, ep, payload, unit):
    if "character" in unit:
        return round(len(payload.get(TEXT_FIELD, "")) / 1000, 3)
    return 1


if a.dry_run:
    for label, (ep, p) in jobs.items():
        print(f"  {label}: {ep} -> {p.get(TEXT_FIELD) or p.get('prompt')}")
    falq.estimate(jobs, units)
    sys.exit(0)

for label, res in falq.run_many(jobs).items():
    if isinstance(res, Exception):
        continue
    dest = os.path.join(a.project, "audio", f"{label}.mp3")
    P.keep_previous(dest)
    falq.download(falq.first_url(res), dest)
    P.log(a.project, label, jobs[label][1], res)
print("audio:", ", ".join(jobs))
