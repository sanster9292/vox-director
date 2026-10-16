#!/usr/bin/env python3
"""Stage 1b: re-render approved keyframes at 2K with crisp, natural-looking people, same layout.

Run this after you've approved the 1K keyframes and before animating. Faces at 1K are only a
few dozen pixels tall, which is the main reason people look blurry and "AI" once animated.
Optionally pass --fix "instruction" with --ids to make one targeted correction instead
(e.g. "move the tower down so it no longer covers the headline").

  python3 scripts/hires.py <project> [--ids 1,4] [--fix "..."] [--dry-run]
"""
import os
import sys

import falq
import project as P

a = P.args("2K re-render / targeted fix of keyframes",
           lambda p: p.add_argument("--fix", help="one targeted edit instruction instead of the 2K pass"))
doc, st = P.load(a.project), P.state(a.project)
if a.draft and not a.fix:
    sys.exit("draft pass: skipping the 2K re-render (it only matters for the final film). "
             "Go straight to clips.py --draft.")
# Locking in a draft: final 2K renders start from the approved draft keyframes, keeping their layout.
draft_state = P.state(os.path.join(a.project, "draft")) if not a.draft else {}
EDIT = P.need(doc, "image", "edit_model")
RES = doc.get("image", {}).get("hires_resolution", "2K")

HIRES = ("Re-render this exact collage poster at higher resolution. Keep the layout, every element's "
         "position and size, the colours, the paper textures and the headline text exactly as they are. "
         "Improve only the people: make every person a crisp, sharp, natural-looking PRINTED PHOTOGRAPH "
         "cut-out of a real person, with realistic skin texture, natural facial features, clear eyes, "
         "believable hands and fabric folds, and fine halftone print grain, like faces clipped from a "
         "high-quality newspaper photo. Keep buildings and vehicles crisp and detailed too.")

jobs = {}
for b in P.selected(doc, a.ids):
    label = f"beat{b['id']}"
    if label not in st and label in draft_state:
        st[label] = draft_state[label]
        print(f"{label}: starting from the approved draft keyframe", file=sys.stderr)
    if label not in st:
        sys.exit(f"{label}: no keyframe yet; run keyframes.py first")
    prompt = (f"Keep this collage poster exactly the same in every detail, except: {a.fix} Change nothing else."
              if a.fix else HIRES)
    jobs[label] = (EDIT, falq.fit(EDIT, {"prompt": prompt, "image_urls": [st[label]],
                                         "aspect_ratio": doc.get("aspect", "9:16"), "resolution": RES,
                                         "num_images": 1, "output_format": "png"}))

if a.dry_run:
    falq.estimate(jobs, lambda *_: 1)
    sys.exit(0)

for label, res in falq.run_many(jobs).items():
    if isinstance(res, Exception):
        continue
    dest = os.path.join(a.project, "keyframes", f"{label}.png")
    P.keep_previous(dest)
    st[label] = falq.first_url(res)
    falq.download(st[label], dest)
    P.log(a.project, f"{label}_{'fix' if a.fix else 'hires'}", jobs[label][1], res)
    P.save_state(a.project, st)
print("done:", ", ".join(jobs))
