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
TEXT_FIELD = tts.get("text_field", "prompt")   # fit() moves it if the model reads "text" instead
TTS_PARAMS = tts.get("params", {})
music = doc.get("music", {})
OWN_MUSIC = os.path.join(a.project, "audio", "music.mp3")

jobs = {}
if a.only != "music":
    for b in P.selected(doc, a.ids):
        if b.get("narration"):
            m = P.need(doc, "tts")
            jobs[f"vo{b['id']}"] = (m, falq.fit(m, dict({TEXT_FIELD: b["narration"]}, **TTS_PARAMS)))
if a.only != "tts" and not a.ids and os.path.exists(OWN_MUSIC) and a.only != "music":
    print(f"  music: reusing {OWN_MUSIC} (delete it or pass --only music to generate one)")
elif a.only != "tts" and not a.ids and music.get("prompt"):
    m = P.need(doc, "music")
    jobs["music"] = (m, falq.fit(m, dict({"prompt": music["prompt"], "is_instrumental": True},
                                         **music.get("params", {}))))


def units(label, ep, payload, unit):
    if "character" in unit:
        text = payload.get(TEXT_FIELD) or payload.get("prompt") or payload.get("text") or ""
        return round(len(text) / 1000, 3)
    return 1


if a.dry_run:
    for label, (ep, p) in jobs.items():
        print(f"  {label}: {ep} -> {p.get(TEXT_FIELD) or p.get('prompt') or p.get('text')}")
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
