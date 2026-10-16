#!/usr/bin/env python3
"""Stage 5: cut the film together with ffmpeg -> <project>/final.mp4

- one segment per beat; a segment lasts max(clip length, narration + breathing room)
- clips shorter than their segment are slowed (setpts), never freeze-framed
- clips are scaled to cover the canvas and centre-cropped (1080x1920 for 9:16, 1920x1080 for 16:9)
- captions overlay in the lower safe area while the line is spoken
- narration lines are placed on their own beats; music is ducked under them (sidechain)

  python3 scripts/assemble.py <project>
beats.json "mix": {"music": 0.6, "voice": 1.25} adjusts the balance; "captions": false skips captions.
"""
import os
import subprocess
import sys

import project as P

a = P.args("Assemble final.mp4")
doc = P.load(a.project)
W, H = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080),
        "4:5": (1080, 1350), "3:4": (1080, 1440)}[doc.get("aspect", "9:16")]
VO_LEAD, TAIL, END_HOLD = 0.15, 0.35, 0.8
mix = doc.get("mix", {})
use_caps = doc.get("captions", True)
J = lambda *p: os.path.join(a.project, *p)


def probe(path, entry="format=duration"):
    return subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", entry,
                                    "-of", "csv=p=0", path]).decode().strip()


segs = []
for i, b in enumerate(doc["beats"]):
    n = b["id"]
    clip = J("clips", f"clip{n}.mp4")
    if not os.path.exists(clip):
        sys.exit(f"missing clips/clip{n}.mp4; run clips.py first")
    vo = J("audio", f"vo{n}.mp3")
    cap = J("captions", f"cap{n}.png")
    cd = float(probe(clip))
    vd = float(probe(vo)) if os.path.exists(vo) else 0.0
    seg = max(cd, VO_LEAD + vd + TAIL if vd else cd) + (END_HOLD if i == len(doc["beats"]) - 1 else 0)
    segs.append(dict(n=n, clip=clip, cd=cd, seg=seg,
                     vo=vo if vd else None, vd=vd,
                     cap=cap if use_caps and os.path.exists(cap) else None))

args, f, idx = ["ffmpeg", "-v", "error", "-y"], [], 0
for s in segs:
    args += ["-i", s["clip"]]
    s["vi"], idx = idx, idx + 1
for s in segs:
    if s["vo"]:
        args += ["-i", s["vo"]]
        s["ai"], idx = idx, idx + 1
for s in segs:
    if s["cap"]:
        args += ["-loop", "1", "-i", s["cap"]]
        s["ci"], idx = idx, idx + 1
music = J("audio", "music.mp3")
mi = None
if os.path.exists(music):
    args += ["-i", music]
    mi = idx

total = sum(s["seg"] for s in segs)
for j, s in enumerate(segs):
    f.append(f"[{s['vi']}:v]setpts={s['seg'] / s['cd']:.5f}*PTS,fps=24,"
             f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
             f"crop={W}:{H},setsar=1,trim=duration={s['seg']:.3f}[v{j}]")
    if s["cap"]:
        ch = int(probe(s["cap"], "stream=height"))
        y = int(H * (0.79 if H > W else 0.84) - ch / 2)
        t0, t1 = VO_LEAD, s["seg"] - 0.05
        f.append(f"[{s['ci']}:v]format=rgba,trim=duration={s['seg']:.3f}[c{j}]")
        f.append(f"[v{j}][c{j}]overlay=0:{y}:enable='between(t,{t0},{t1:.3f})':shortest=1,format=yuv420p[o{j}]")
    else:
        f.append(f"[v{j}]format=yuv420p[o{j}]")
f.append("".join(f"[o{j}]" for j in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[vout]")

start, vo_labels = 0.0, []
for j, s in enumerate(segs):
    if s["vo"]:
        d = int((start + VO_LEAD) * 1000)
        f.append(f"[{s['ai']}:a]aresample=48000,adelay={d}|{d},apad[vo{j}]")
        vo_labels.append(f"[vo{j}]")
    start += s["seg"]

maps = ["-map", "[vout]"]
if vo_labels:
    f.append("".join(vo_labels) + f"amix=inputs={len(vo_labels)}:normalize=0,"
             f"atrim=duration={total:.3f},volume={mix.get('voice', 1.25)},asplit=2[vox][sc]")
if mi is not None:
    f.append(f"[{mi}:a]aresample=48000,apad,atrim=duration={total:.3f},volume={mix.get('music', 0.6)},"
             f"afade=t=in:d=0.4,afade=t=out:st={max(total - 1.8, 0):.3f}:d=1.8[mus]")
if vo_labels and mi is not None:
    f.append("[mus][sc]sidechaincompress=threshold=0.05:ratio=6:attack=20:release=300[duck]")
    f.append("[duck][vox]amix=inputs=2:normalize=0,alimiter=limit=0.95[aout]")
elif vo_labels:
    f.append("[sc]anullsink;[vox]alimiter=limit=0.95[aout]")
elif mi is not None:
    f.append("[mus]alimiter=limit=0.95[aout]")
if vo_labels or mi is not None:
    maps += ["-map", "[aout]"]

out = J("final.mp4")
P.keep_previous(out)
subprocess.run(args + ["-filter_complex", ";".join(f)] + maps +
               ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", out],
               check=True)
print(f"{out}  {W}x{H}  {total:.2f}s")
for s in segs:
    stretch = f"  (slowed {s['seg'] / s['cd']:.2f}x)" if s["seg"] > s["cd"] + 0.05 else ""
    print(f"  beat {s['n']}: clip {s['cd']:.2f}s, narration {s['vd']:.2f}s -> {s['seg']:.2f}s{stretch}")
