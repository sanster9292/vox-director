---
name: vox-director-fal
description: "Turn a topic into a finished Vox-style paper-collage video (torn paper, halftone cut-outs, bold flat colour, baked-in headlines) with narration, music and captions, end to end on fal.ai + local ffmpeg. Use this whenever someone wants a Vox-style or collage explainer, a motion collage, a narrated paper-collage short or ad, a city/place/brand/history piece told as layered collage posters, or a vertical collage Reel/Short, even if they never say 'Vox'. Handles real landmarks from reference photos, crisp photographic people, and mixed-language narration (e.g. Urdu + English). Prefer this over an Atlas Cloud collage skill whenever the person has a fal key or mentions fal, MiniMax H3, nano-banana or Gemini TTS."
---

# Vox Director (fal edition)

Turns one topic into a finished **Vox-style paper-collage film**: each beat is a torn-paper
collage poster with a baked-in headline, animated by an image-to-video model, then cut together
with narration, a music bed and captions. All generation runs on **fal.ai**; editing runs on
local **ffmpeg**.

How the look works: **the collage look is born in the image step** (a rich, layered poster with
clear cut-out edges and shadows), and **motion is added after** by animating that poster. A weak
keyframe can't be rescued by animation, so most of the care goes into keyframes, and keyframes
are cheap to re-roll. Before writing any image or motion prompt, read
`references/prompt-guide.md` (prompt structure, vocabulary, theme presets). For the story
side (arcs, hooks, pacing), read `references/beat-layer.md`. For models, prices and every known
failure, read `references/fal-models.md`.

## Before anything: prerequisites

- **fal key.** Scripts read `FAL_KEY`, or on macOS a Keychain item named `fal-api-key`. If neither
  exists, ask the person to run `zsh scripts/set_fal_key.sh` **in their own terminal** (it hides
  the key while they type), or to export `FAL_KEY` themselves. Don't ask them to paste a key into the
  chat, because chat transcripts are not a safe place for secrets. If they paste one anyway, use it,
  store it via the Keychain script, and suggest they rotate it later.
- **ffmpeg + ffprobe** (`brew install ffmpeg` / apt). Python 3 standard library is enough.
- **Captions:** on macOS the Swift renderer compiles itself on first use (needs Xcode command line
  tools). Elsewhere `pip install pillow`. Or set `"captions": false`.
- **Where to save.** Ask where the person wants their videos, or use `~/Videos/vox/<project>/`.
  One folder per project. Everything (keyframes, clips, audio, prompts, review sheets) stays inside it.

All scripts live in this skill's `scripts/` folder and take the project folder as the first argument:
`python3 <skill>/scripts/keyframes.py <project>`. Every paid stage supports `--dry-run` (prints the
jobs and a cost estimate, submits nothing) and `--ids 1,4` (redo only those beats).

## Workflow

### 1. Beat map → approval gate
Write `<project>/beats.json` (schema below; a full working example is in
`examples/faisalabad-30s-9x16-ur-en.beats.json`). Then **show the person the beat map as a table**
(headline, narration, what's in the collage, camera/motion) plus the estimated cost, and wait for
their go-ahead or edits. This is the cheapest moment to change direction.

- Ask what's unclear and matters: aspect (9:16 for Reels/Shorts, 16:9 for YouTube), length,
  language(s) of the narration, and whether to focus on history or present day.
- ~5 s per beat; 30 s ≈ 6 beats. Keep each narration line to what fits ~5 s (≈12 English words);
  longer lines make `assemble.py` slow the clip down.
- Beat 1's headline is the hook. Vary `camera` between adjacent beats; finish on a hold.
- **Make it specific and recognisable.** Name real places, foods, vehicles, crafts and everyday
  people (shopkeepers, students, a chaiwala, cricket fans). Generic collage reads as stock.
- Feature everyday people, not named celebrities: video models often refuse recognisable public
  figures, and the person usually wants "the people of X" anyway.

### 2. Reference photos for real landmarks
If a beat shows a **named real place** (a clock tower, a gate, a stadium, a university), the image
model will otherwise invent a plausible-looking but wrong building. Fetch real photos first:

```bash
python3 scripts/refs.py search "Clock Tower Faisalabad"
python3 scripts/refs.py get <project> clocktower.jpg "File:Clock tower in Faisalabad, Pakistan, 2011.jpg"
python3 scripts/refs.py sheet <project>     # look at references/ before using them
```
Then add `"refs": [{"file": "clocktower.jpg", "desc": "the red sandstone Ghanta Ghar clock tower..."}]`
to that beat. The `desc` matters: say what the photo shows and which details to keep. Prefer clear
daytime photos of the building itself. Overhead shots work well for "streets radiating out" scenes.
Commons photos are freely licensed but most require **credit**: `get` appends each one to
`references/CREDITS.md`. Tell the person to credit the photographers if they publish the video.

### 3. Keyframes (1K) → look → fix
```bash
python3 scripts/keyframes.py <project> --dry-run    # check prompts + cost
python3 scripts/keyframes.py <project>
python3 scripts/review.py <project> keyframes        # then Read the sheet image
```
Look at every keyframe before spending on video. Check: headline spelled right with no stray
quotes and nothing poking into the banner; dense layered cut-outs (not a smooth painting); the
landmark matches its reference; the bottom fifth calm enough for captions. Re-roll one beat with
`--ids N` (~$0.08), or make one targeted fix that keeps the rest:
`python3 scripts/hires.py <project> --ids 1 --fix "move the tower down so its spire no longer covers the headline"`.

### 4. 2K pass for crisp people
```bash
python3 scripts/hires.py <project>
```
Re-renders each approved keyframe at 2K with the layout kept and people made into sharp, natural
printed-photo cut-outs. Skipping this is the main cause of blurry, "AI-looking" faces in the final
film: at 1K a face is only a few dozen pixels tall before animation even starts. Look at the
sheet again; the edit model occasionally nudges an element.

### 5. Clips → look at every one
```bash
python3 scripts/clips.py <project> --dry-run
python3 scripts/clips.py <project>
python3 scripts/review.py <project> clips
python3 scripts/review.py <project> title <beat>     # for any clip where something moves near the top
```
Default model: MiniMax H3 Max Turbo at 1080P (people stay sharp). 480P is cheaper but visibly soft.
The usual defect is **something drifting over the headline** (smoke, kites, petals, unrolling
cloth). Fix it by rewriting that beat's `motion` to keep the moving thing in the lower part of
the frame ("the kites stay in the sky band below the banner"), then `--ids N` to re-roll. Earlier
takes are kept as `clipN_take1.mp4`, so nothing is lost.

### 6. Narration + music
```bash
python3 scripts/audio.py <project>
```
One narration file per beat so each line lands on its own cut. Pick the voice and delivery to fit
the topic (`tts.params`). For **code-switched narration** (Urdu + English, Hindi + English, ...),
Gemini TTS handles it well: write each language in its own script inside `narration` (e.g.
`"Welcome to Faisalabad. پاکستان کا تیسرا سب سے بڑا شہر۔"`) and describe the accent in
`style_instructions`. Music: an instrumental prompt that names instruments from the topic's culture.

### 7. Captions
```bash
python3 scripts/captions.py <project>
```
Captions use each beat's `caption`, falling back to `narration`. For mixed-script narration, write
`caption` in **Latin script** (Roman Urdu / Hinglish): mixed right-to-left and left-to-right text
reads in a jumbled order whenever a line wraps.

### 8. Assemble + verify
```bash
python3 scripts/assemble.py <project>
python3 scripts/review.py <project> final
```
You can't watch the mp4, so look at the sheet, and say plainly that you couldn't *listen* to it.
Ask the person to check the pronunciation, especially for non-English lines (re-doing one line costs
about a cent: `audio.py --ids N --only tts`, then `assemble.py`).

When reporting back: give the full path to `final.mp4`, a one-line summary per beat, what you fixed
along the way, anything still imperfect, the photo-credit note if refs were used, and the
approximate total spend (quote a range: fal's pricing API shows base-tier prices).

## beats.json schema

```json
{
  "project": "welcome-to-faisalabad",
  "topic": "...", "language": "ur+en", "aspect": "9:16",
  "feel": "bustling, joyful, proud city energy",
  "style_block": "Mixed-media hand-cut PAPER COLLAGE ... (identical for every beat; see prompt-guide §1)",
  "image": {"model": "fal-ai/nano-banana-2", "edit_model": "fal-ai/nano-banana-2/edit",
            "resolution": "1K", "hires_resolution": "2K"},
  "video": {"model": "minimax/h3-max-turbo/image-to-video", "duration": 5, "params": {"resolution": "1080P"}},
  "tts":   {"model": "google/gemini-3.8-flash-tts", "text_field": "prompt",
            "params": {"voice": "Charon", "style_instructions": "warm, proud documentary narrator..."}},
  "music": {"model": "fal-ai/minimax-music/v2.6", "prompt": "upbeat ... instrumental, no vocals"},
  "mix": {"music": 0.6, "voice": 1.25},
  "captions": true,
  "beats": [
    {"id": 1, "title": "WELCOME TO FAISALABAD", "subtitle": "optional small line",
     "bg": "bold truck-art red",
     "narration": "what the voice says (any script)",
     "caption": "optional on-screen text if it should differ from narration",
     "scene": "the cut-out pieces in this poster: subject, people, props, decorative scraps",
     "camera": "slow smooth push-in",
     "motion": "what moves inside the frame, and where (keep it off the headline)",
     "refs": [{"file": "clocktower.jpg", "desc": "what the photo shows / what to keep"}],
     "duration": 5}
  ]
}
```
Only `style_block` and the beat fields `id`, `bg`, `scene`, `camera`, `motion` are required; the
rest have the defaults shown. Write the style block so it also asks for: people as PRINTED-texture
photo cut-outs (not CGI), every piece a distinct cut-out with its own shadow, the headline in the
top fifth and a calmer bottom fifth for captions.

## Costs and asking first

Every paid stage costs real money on the person's fal account. Show the `--dry-run` estimate when
you present the beat map, and again before the clip stage (the expensive one, roughly 70% of the
total). Re-rolls are normal: budget one or two per film. If a stage fails with 401/403 the key is
wrong; 402 or "insufficient balance" means the account needs credit, so stop and tell the person
rather than retrying.

## Not in this edition

The original Atlas Cloud `vox-director` also has A-roll (re-style a talking-head video), C-roll
(anchor one photo of a person/product), host mode and a local element-by-element motion engine.
Those aren't ported to fal yet. If someone needs them, say so and point them to the Atlas edition.
