# Vox Director (fal.ai edition)

**One topic in, one finished Vox-style paper-collage film out:** script, collage keyframes,
motion, narration, music and captions, generated on [fal.ai](https://fal.ai) and cut together with
local `ffmpeg`.

![License: MIT](https://img.shields.io/badge/License-MIT-black.svg) ![Runs on fal.ai](https://img.shields.io/badge/runs%20on-fal.ai-5b3df5.svg) ![Agent Skill](https://img.shields.io/badge/Agent-Skill-d97757.svg)

This is a fork of **[Alisa0808/vox-director](https://github.com/Alisa0808/vox-director)**, the
original Atlas Cloud skill. This edition moves the pipeline to fal.ai and lets each project pick
its own models. See [`CHANGES.md`](CHANGES.md) for every change and the reason for it.

## What it is

An **agent skill**: a workflow in [`SKILL.md`](SKILL.md) plus one Python script per stage. A coding
agent (Claude Code, Codex, anything that reads `SKILL.md`) follows it to make the film. Each beat
is a torn-paper collage poster with a baked-in headline. An image-to-video model animates it, and
the beats are cut together with a voice-over, a music bed and captions.

The look is made in the image step, and motion is added afterwards. Most of the care goes into
the keyframes, which are cheap to re-roll; animation can't rescue a weak poster.

It triggers **only** when you ask for a Vox-style video. Other collage or motion-graphics requests
are left to other tools.

## Install

```bash
git clone https://github.com/sanster9292/vox-director.git ~/.claude/skills/vox-director-fal
brew install ffmpeg            # or apt install ffmpeg; Python 3 standard library is enough
```

Claude Code picks the skill up from `SKILL.md`'s frontmatter. Other agents: point them at `SKILL.md`.
For captions, macOS compiles the bundled Swift renderer on first use (Xcode command line tools);
elsewhere `pip install pillow`, or set `"captions": false`.

### Keys

| Key | Needed for | Set it with |
|---|---|---|
| fal.ai ([get one](https://fal.ai/dashboard/keys)) | every paid stage | `zsh scripts/set_key.sh fal-api-key` or `export FAL_KEY=...` |
| Pexels ([free](https://www.pexels.com/api/)) | optional photo search | `zsh scripts/set_key.sh pexels-api-key` or `PEXELS_API_KEY` |
| Google Places API (New) | optional place-photo search | `zsh scripts/set_key.sh google-maps-api-key` or `GOOGLE_MAPS_API_KEY` |

`set_key.sh` stores the key in the macOS Keychain with hidden typing. Run it in your own terminal
so the key never lands in a chat or your shell history. (`set_fal_key.sh` still works and calls it.)

## Quick start

Ask your agent, with the skill installed:

> *"Make a Vox-style video about Faisalabad: 30 seconds, 9:16, Urdu and English narration."*

The agent writes a beat map (`beats.json`) and shows it to you as a table, together with the
models it picked, their licences and a cost estimate. Nothing is spent until you approve.
It then runs the stages:

```bash
python3 scripts/refs.py ...       <project>   # real photos of real places (yours first)
python3 scripts/keyframes.py      <project>   # 1K collage posters → review → fix
python3 scripts/hires.py          <project>   # 2K pass so faces stay crisp
python3 scripts/clips.py          <project>   # animate each poster
python3 scripts/audio.py          <project>   # narration per beat + music
python3 scripts/captions.py       <project>
python3 scripts/assemble.py       <project>   # → <project>/final.mp4
python3 scripts/review.py <project> keyframes|clips|final   # contact sheets to check
```

Every paid stage takes `--dry-run` (prints the jobs and the cost, submits nothing) and `--ids 1,4`
(redo only those beats). [`examples/faisalabad-30s-9x16-ur-en.beats.json`](examples/faisalabad-30s-9x16-ur-en.beats.json)
is a full working beat map.

## Draft → final

Before you pay for the real film, you can try ideas on a cheap draft:

1. **Draft.** Run each stage with `--draft`. It works in `<project>/draft/` (linked to the same
   `beats.json` and `references/`). It skips the 2K pass, renders video at 480P, and uses any
   cheaper models you put in a `"draft"` block of `beats.json`, e.g.
   `"draft": {"image": {"model": "fal-ai/flux-2/klein/4b", "edit_model": "fal-ai/flux-2/klein/4b/edit"}}`.
2. **Lock in.** Once the draft is approved, run `hires.py` without `--draft`. It starts from the
   approved draft keyframes, so the layout stays, and renders them at 2K. Then run `clips.py`,
   `audio.py`, `captions.py` and `assemble.py` as usual.

## Models: none built in

The scripts don't default to any model. Each project names its own in `beats.json` (`image.model`,
`image.edit_model`, `video.model`, `tts.model`, and `music.model` unless you supply
`audio/music.mp3`). A stage with no model stops and tells you which field to fill. How the models
are picked:

1. **Your choice wins.**
2. **Open source first,** whatever the country of origin: permissive licences first, then open
   weights with a non-commercial self-host licence, then closed models only when no open one does the job.
3. **Then the cheapest** open model that passes a one-keyframe test, at the cheapest settings that
   still look right. Drafts use the cheapest open model outright.

Models name the same input differently (`image_size` vs `aspect_ratio`, `image_url` vs
`image_urls`, `prompt` vs `text`). `falq.fit()` reads each endpoint's input schema and reshapes the
request to match, so switching models only takes a `beats.json` edit. Candidates, prices, licences
and known failures are in [`references/fal-models.md`](references/fal-models.md).

## Real places look real

When a beat shows a real street, landmark or shop, the image model gets real photos as references.
`refs.py add` saves your own photos first. The skill searches the web only after you say yes, in
this order: Google Maps place photos, Pexels, Wikimedia Commons photos geotagged at the place,
then Commons keyword search. Every saved photo gets a line in `references/CREDITS.md`. People are
never searched for: photos of a real person come only from you, with their consent.

## What's in the box

```
SKILL.md        the workflow the agent follows
scripts/        falq.py (fal queue client + fit()), project.py (args, draft, need()),
                one script per stage, refs.py, review.py, set_key.sh
references/     fal-models.md (models, rules, prices, gotchas), prompt-guide.md, beat-layer.md
examples/       a full beat map (Faisalabad, 30 s, 9:16, Urdu + English)
docs/           annotated.html: the skill with margin notes explaining each decision
assets/         showcase films from the original Atlas edition
```

## Credits

- **Original skill:** [Alisa0808/vox-director](https://github.com/Alisa0808/vox-director) by
  [@alisaqqt](https://x.com/alisaqqt): the workflow, prompt guide, beat library and showcase films.
- That project credits **Stav Zilber**, **rom1trs** and **Higgsfield** for the collage-ad workflow,
  and **[Vox](https://www.vox.com)** for the visual language.
- fal.ai edition by [sanster9292](https://github.com/sanster9292), built with Claude Opus 5.5
  (details in [`CHANGES.md`](CHANGES.md#credits)).

## License

[MIT](LICENSE). Original © 2026 Alisa Qian; the fal.ai edition's changes are released under the same licence.
