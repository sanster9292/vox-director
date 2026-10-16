#!/usr/bin/env python3
"""Contact sheets for looking at results (you can't watch an mp4, so look at these instead).

  python3 scripts/review.py <project> keyframes      # all keyframes side by side
  python3 scripts/review.py <project> clips          # each clip as a strip of 6 frames, stacked
  python3 scripts/review.py <project> final          # one frame from the middle of every beat
  python3 scripts/review.py <project> title <beat>   # top banner of keyframe + last clip frame, to check the headline
Writes into <project>/review/ and prints the path.
"""
import glob
import json
import os
import subprocess
import sys

proj, what = sys.argv[1], sys.argv[2]
R = lambda *p: os.path.join(proj, *p)
os.makedirs(R("review"), exist_ok=True)
ff = lambda *a: subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)
ids = [b["id"] for b in json.load(open(R("beats.json")))["beats"]]

if what == "keyframes":
    files = [R("keyframes", f"beat{i}.png") for i in ids if os.path.exists(R("keyframes", f"beat{i}.png"))]
    ins = sum([["-i", x] for x in files], [])
    chain = "".join(f"[{i}]scale=340:-2[s{i}];" for i in range(len(files))) + \
        "".join(f"[s{i}]" for i in range(len(files))) + f"hstack={len(files)}"
    out = R("review", "keyframes_sheet.jpg")
    ff(*ins, "-filter_complex", chain if len(files) > 1 else "[0]scale=340:-2", out)
elif what == "clips":
    rows = []
    for i in ids:
        c = R("clips", f"clip{i}.mp4")
        if os.path.exists(c):
            row = R("review", f"clip{i}_strip.jpg")
            ff("-i", c, "-vf", "fps=1.2,scale=200:-1,tile=6x1", "-frames:v", "1", "-update", "1", row)
            rows.append(row)
    out = R("review", "clips_sheet.jpg")
    ff(*sum([["-i", r] for r in rows], []), "-filter_complex", f"vstack={len(rows)}" if len(rows) > 1 else "null", out)
elif what == "final":
    beats = json.load(open(R("beats.json")))["beats"]
    # sample the middle of each segment using the clip lengths as an approximation
    t, picks = 0.0, []
    for b in beats:
        d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                           "-of", "csv=p=0", R("clips", f"clip{b['id']}.mp4")]))
        picks.append(t + d * 0.6)
        t += d
    frames = []
    for k, ts in enumerate(picks):
        fr = R("review", f"final_{k}.jpg")
        ff("-ss", f"{ts:.2f}", "-i", R("final.mp4"), "-frames:v", "1", "-vf", "scale=300:-1,format=yuvj420p", fr)
        frames.append(fr)
    out = R("review", "final_sheet.jpg")
    ff(*sum([["-i", x] for x in frames], []), "-filter_complex", f"hstack={len(frames)}", out)
elif what == "title":
    n = sys.argv[3]
    out = R("review", f"title_beat{n}.jpg")
    kf, clip = R("keyframes", f"beat{n}.png"), R("clips", f"clip{n}.mp4")
    ff("-i", kf, "-vf", "scale=900:-2,crop=900:ih*0.16:0:0", R("review", "_t1.jpg"))
    if os.path.exists(clip):
        ff("-sseof", "-0.2", "-i", clip, "-frames:v", "1", "-update", "1",
           "-vf", "scale=900:-2,crop=900:ih*0.16:0:0,format=yuvj420p", R("review", "_t2.jpg"))
        ff("-i", R("review", "_t1.jpg"), "-i", R("review", "_t2.jpg"), "-filter_complex", "vstack", out)
    else:
        os.replace(R("review", "_t1.jpg"), out)
else:
    sys.exit(__doc__)
for tmp in glob.glob(R("review", "_t*.jpg")):
    os.remove(tmp)
print(out)
