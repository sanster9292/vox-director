#!/usr/bin/env python3
"""Stage 2: animate each approved keyframe with an image-to-video model.

The motion prompt follows references/prompt-guide.md section 2 (camera, element motion, feel,
colour, stability anchors). Model-specific inputs come from beats.json "video.params", so the
same script drives MiniMax H3, Gemini Omni, Kling, Seedance etc.

  python3 scripts/clips.py <project> [--ids 3] [--dry-run]
"""
import os
import sys

import falq
import project as P

a = P.args("Animate keyframes")
doc, st = P.load(a.project), P.state(a.project)
vid = doc.get("video", {})
MODEL = P.need(doc, "video")
PARAMS = vid.get("params", {})
DUR = vid.get("duration", 5)


def motion_prompt(b):
    title_lock = ("The headline banner at the top stays sharp, legible and perfectly still, and nothing "
                  "moves over it. " if b.get("title") else "")
    return (f"Animate this still into a flat 2D paper-cutout collage motion graphic, rigid paper layers. "
            f"Camera: {b['camera']}, one smooth continuous move, gentle and slow. "
            f"Movement: {b['motion']}; layered cut-outs parallax with visible drop shadows, torn edges and "
            f"tape flutter slightly, halftone grain stays. "
            f"Feel: {b.get('feel', doc.get('feel', 'lively, editorial'))}. "
            f"Colour: keep the bold flat {b['bg']} background and the palette of the still. "
            f"{title_lock}Every person keeps the same face and clothing throughout. "
            f"Single continuous shot, camera stays parallel to the poster, paper pieces slide and pivot "
            f"as flat rigid paper, then the motion eases and settles.")


jobs = {}
for b in P.selected(doc, a.ids):
    label = f"beat{b['id']}"
    if label not in st and not a.dry_run:
        sys.exit(f"{label}: no keyframe URL in state.json; run keyframes.py first")
    jobs[f"clip{b['id']}"] = (MODEL, falq.fit(MODEL, dict({"prompt": motion_prompt(b),
                                                         "image_url": st.get(label, "<keyframe>"),
                                                         "duration": b.get("duration", DUR)}, **PARAMS)))

def secs_of(p):
    return float(str(p.get("duration", DUR)).rstrip("s"))


# fal's pricing API only reports the base (lowest-resolution, often promo) tier, which badly
# under-quotes higher resolutions. List prices per second by resolution, from the model pages (Oct 2026).
# beats.json "video.price_per_second" overrides this.
TIERS = {
    "minimax/h3-max-turbo/image-to-video": {"480P": 0.025, "768P": 0.04, "1080P": 0.08},
    "minimax/h3-max/image-to-video": {"480P": 0.05, "768P": 0.08, "1080P": 0.16},
    "google/gemini-omni-flash/image-to-video": {"720p": 0.13},
}

if a.dry_run:
    for label, (ep, p) in jobs.items():
        print(f"--- {label} via {ep} {PARAMS}\n{p.get('prompt', '')}\n")
    pps = vid.get("price_per_second") or TIERS.get(MODEL, {}).get(PARAMS.get("resolution", ""))
    if pps:
        secs = sum(secs_of(p) for _, p in jobs.values())
        print(f"  {len(jobs)} clips x {DUR}s at ${pps}/s ({MODEL} {PARAMS.get('resolution', '')}, list price) "
              f"= ${pps * secs:.2f}\n  (launch promos can make it cheaper; check https://fal.ai/models/{MODEL})")
    else:
        falq.estimate(jobs, lambda l, e, p, unit: secs_of(p) if "second" in unit else 1)
    sys.exit(0)

for label, res in falq.run_many(jobs).items():
    if isinstance(res, Exception):
        continue
    dest = os.path.join(a.project, "clips", f"{label}.mp4")
    P.keep_previous(dest)
    falq.download(falq.first_url(res), dest)
    P.log(a.project, label, jobs[label][1], res)
print("clips:", ", ".join(f"{k}={'FAILED' if not os.path.exists(os.path.join(a.project, 'clips', k + '.mp4')) else 'ok'}" for k in jobs))
