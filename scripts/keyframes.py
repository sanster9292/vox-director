#!/usr/bin/env python3
"""Stage 1: one collage keyframe per beat.

Beats with "refs" (real reference photos in <project>/references/) go through the image EDIT
model so named landmarks look like the real place; beats without refs use text-to-image.

  python3 scripts/keyframes.py <project> [--ids 1,4] [--dry-run]
"""
import base64
import os
import subprocess
import sys
import tempfile

import falq
import project as P

a = P.args("Generate collage keyframes")
doc, st = P.load(a.project), P.state(a.project)
img = doc.get("image", {})
T2I = img.get("model", "fal-ai/nano-banana-2")
EDIT = img.get("edit_model", "fal-ai/nano-banana-2/edit")
RES = img.get("resolution", "1K")
aspect = doc.get("aspect", "9:16")
tmp = tempfile.mkdtemp()


def data_uri(path):
    """Inline a local reference photo (downscaled to <=1024px) as a JPEG data URI."""
    small = os.path.join(tmp, os.path.basename(path) + ".jpg")
    if sys.platform == "darwin":
        subprocess.run(["sips", "-Z", "1024", "-s", "format", "jpeg", path, "--out", small],
                       check=True, capture_output=True)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf",
                        "scale='min(1024,iw)':-2", small], check=True)
    return "data:image/jpeg;base64," + base64.b64encode(open(small, "rb").read()).decode()


def prompt_for(b):
    sub = f' with a small subtitle "{b["subtitle"]}"' if b.get("subtitle") else ""
    headline = (f'A torn-paper banner at the top with a big bold condensed all-caps headline '
                f'"{b["title"]}"{sub}, spelled exactly. ' if b.get("title") else "")
    body = (f'{doc["style_block"]} SCENE as layered paper cut-outs: {b["scene"]}. '
            f'On a bold flat {b["bg"]} paper background. {headline}Aspect ratio {aspect}.')
    if not b.get("refs"):
        return body
    refs = " ".join(f"Reference image {i + 1} is a photo of {r['desc']}." for i, r in enumerate(b["refs"]))
    return (f"{refs} Recreate those real landmarks faithfully (same architecture, shape, colour, "
            f"domes, arches, clock faces) as printed halftone photo cut-outs inside a brand-new collage "
            f"poster. Take only the buildings from the references; leave out their photo backgrounds, "
            f"cars, signboards, advertising and logos. " + body)


jobs = {}
for b in P.selected(doc, a.ids):
    label = f"beat{b['id']}"
    payload = {"prompt": prompt_for(b), "aspect_ratio": aspect, "resolution": RES,
               "num_images": 1, "output_format": "png"}
    if b.get("refs"):
        missing = [r["file"] for r in b["refs"]
                   if not os.path.exists(os.path.join(a.project, "references", r["file"]))]
        if missing:
            sys.exit(f"{label}: missing reference photos in references/: {missing}")
        payload["image_urls"] = ([] if a.dry_run else
                                 [data_uri(os.path.join(a.project, "references", r["file"]))
                                  for r in b["refs"]])
        jobs[label] = (EDIT, payload)
    else:
        jobs[label] = (T2I, payload)

if a.dry_run:
    for label, (ep, p) in jobs.items():
        print(f"--- {label} via {ep}\n{p['prompt']}\n")
    falq.estimate(jobs, lambda *_: 1)
    sys.exit(0)

for label, res in falq.run_many(jobs).items():
    if isinstance(res, Exception):
        continue
    dest = os.path.join(a.project, "keyframes", f"{label}.png")
    P.keep_previous(dest)
    st[label] = falq.first_url(res)
    falq.download(st[label], dest)
    logged = dict(jobs[label][1])
    if "image_urls" in logged:
        logged["image_urls"] = [r["file"] for b in doc["beats"] if f"beat{b['id']}" == label for r in b["refs"]]
    P.log(a.project, f"{label}_keyframe", logged, res)
    P.save_state(a.project, st)
print("keyframes:", ", ".join(f"{k}={'ok' if k in st else 'FAILED'}" for k in jobs))
