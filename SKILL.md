---
name: vox-director-fal
description: "Make a Vox-style video: a narrated explainer or ad built from torn-paper collage posters (halftone cut-outs, bold flat colour, baked-in headlines) with music and captions, end to end on fal.ai + local ffmpeg. Use ONLY when someone asks for a Vox-style or Vox-styled video, or names Vox as the look they want. Don't use it for other collage, motion-graphics or video requests that don't ask for the Vox style. Handles real places from reference photos, crisp photographic people, and mixed-language narration (e.g. Urdu + English)."
---

# Vox Director

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

**No model is built in.** Each project names its models in `beats.json`, chosen when you write
the beat map: the person's pick first, otherwise **open-source models first, whatever country
they come from**. Among the open models that do the job, **pick the cheapest**, and the cheapest
settings that still look right (candidates and rules in `references/fal-models.md`). A stage with
no model stops and says which field to fill. `falq.fit()` adapts each request to the chosen
model's own input fields.

## Before anything: prerequisites

- **fal key.** Scripts read `FAL_KEY`, or on macOS a Keychain item named `fal-api-key`. If neither
  exists, ask the person to run `zsh scripts/set_key.sh fal-api-key` **in their own terminal** (it
  hides the key while they type), or to export `FAL_KEY` themselves. Photo search uses the same
  pattern for `pexels-api-key` and `google-maps-api-key` (both optional). Don't ask them to paste a key into the
  chat, because chat transcripts are not a safe place for secrets. If they paste one anyway, use it,
  store it via the Keychain script, and suggest they rotate it later.
- **ffmpeg + ffprobe** (`brew install ffmpeg` / apt). Python 3 standard library is enough.
- **Captions:** on macOS the Swift renderer compiles itself on first use (needs Xcode command line
  tools). Elsewhere `pip install pillow`. Or set `"captions": false`.
- **Where to save.** Ask where the person wants their videos, or use `~/Videos/vox/<project>/`.
  One folder per project. Everything (keyframes, clips, audio, prompts, review sheets) stays inside it.

All scripts live in this skill's `scripts/` folder and take the project folder as the first argument:
`python3 <skill>/scripts/keyframes.py <project>`. Every paid stage supports `--dry-run` (prints the
jobs and a cost estimate, submits nothing), `--ids 1,4` (redo only those beats) and `--draft`
(a cheap ideation pass in `<project>/draft/`, see step 1).

## Workflow

### 1. Beat map → approval gate
Write `<project>/beats.json` (schema below; a full working example is in
`examples/faisalabad-30s-9x16-ur-en.beats.json`). Then **show the person the beat map as a table**
(headline, narration, what's in the collage, camera/motion), **the model roster with each model's
license**, and the estimated cost, and wait for their go-ahead or edits. This is the cheapest moment to change direction.

**Ask: draft first, or straight to the final film?** A draft is a cheaper, lower-quality pass for
trying ideas before spending on the real one: run every stage with `--draft`. It works in
`<project>/draft/`, skips the 2K pass, renders video at the lowest tier (480P) and uses any cheaper
models set in a `"draft"` block of `beats.json` (for example `"draft": {"image": {"model": ...}}`).
Show both estimates. Once the person approves the draft, lock in: run `hires.py` without `--draft`
(it starts from the approved draft keyframes, so the layout is kept), then `clips.py`, `audio.py`,
`captions.py` and `assemble.py` for the final film. Review a draft with `review.py <project>/draft keyframes`
(or `clips`, `final`).

- Ask what's unclear and matters: aspect (9:16 for Reels/Shorts, 16:9 for YouTube), length,
  language(s) of the narration, and whether to focus on history or present day.
- ~5 s per beat; 30 s ≈ 6 beats. Keep each narration line to what fits ~5 s (≈12 English words);
  longer lines make `assemble.py` slow the clip down.
- Beat 1's headline is the hook. Vary `camera` between adjacent beats; finish on a hold.
- **Make it specific and recognisable.** Name real places, foods, vehicles, crafts and everyday
  people (shopkeepers, students, a chaiwala, cricket fans). Generic collage reads as stock.
- Feature everyday people, not named celebrities: video models often refuse recognisable public
  figures, and the person usually wants "the people of X" anyway.

### 2. Reference photos for real places and people
If a beat shows anything **real and specific** (a city, a street, a landmark, a restaurant or shop,
a real person), the image model will otherwise invent a plausible-looking but wrong one. Get real
photos before generating:

1. **Ask the person for their own photos first.** Save each with
   `python3 scripts/refs.py add <project> shop.jpg ~/Downloads/shop.jpg --credit "their photo"`.
2. **If they have none, ask permission before searching the web.** Only search once they say yes.
3. **Search high-quality sources, in this order:** Google Maps place photos (best for restaurants,
   shops and venues; needs `google-maps-api-key`), Pexels (needs a free `pexels-api-key`), photos
   geotagged at the place on Wikimedia Commons, then Commons keyword search. Without a key, that
   source is skipped and the rest still run.
4. **People are never searched for.** Photos of a real person come only from the person asking,
   with the consent of whoever is pictured.

```bash
python3 scripts/refs.py search "Ghanta Ghar Faisalabad"            # all sources, or --source google|pexels|geo|commons
python3 scripts/refs.py get <project> clocktower.jpg <id from the search results>
python3 scripts/refs.py sheet <project>     # look at references/ before using them
```
Then add `"refs": [{"file": "clocktower.jpg", "desc": "the red sandstone Ghanta Ghar clock tower..."}]`
to that beat. The `desc` matters: say what the photo shows and which details to keep. Prefer clear
daytime photos of the building itself. Overhead shots work well for "streets radiating out" scenes.
Every saved photo gets a line in `references/CREDITS.md` with its source, author and licence.
Commons photos mostly require **credit**; Pexels photos don't but it's polite; Google Maps photos
are used here as references for the image model, so check Google's terms before showing one
unaltered. Tell the person to credit photographers when they publish.

### 3. Keyframes (1K) → look → fix
```bash
python3 scripts/keyframes.py <project> --dry-run    # check prompts + cost (add --draft for the draft pass)
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
Use the resolution that keeps people sharp (1080P on most models); 480P is cheaper but visibly soft.
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
`style_instructions`. Music: drop your own track at `audio/music.mp3` and it is reused, or set `music.model` +
`music.prompt` (an instrumental prompt that names instruments from the topic's culture).

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
  "image": {"model": "<t2i endpoint>", "edit_model": "<edit-with-refs endpoint>",
            "resolution": "1K", "hires_resolution": "2K"},
  "video": {"model": "<image-to-video endpoint>", "duration": 5, "params": {"resolution": "1080P"}},
  "tts":   {"model": "<tts endpoint>", "params": {"voice": "<a voice that model offers>",
            "style_instructions": "warm, proud documentary narrator..."}},
  "music": {"model": "<music endpoint>", "prompt": "upbeat ... instrumental, no vocals"},
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
Required: `style_block`, the beat fields `id`, `bg`, `scene`, `camera`, `motion`, and a model
for each stage you run (`music` is optional when you supply `audio/music.mp3`). Voice names belong
to one TTS model, so pick the voice again whenever you change `tts.model`. Write the style block so it also asks for: people as PRINTED-texture
photo cut-outs (not CGI), every piece a distinct cut-out with its own shadow, the headline in the
top fifth and a calmer bottom fifth for captions.

## Costs and asking first

Every paid stage costs real money on the person's fal account. Show the `--dry-run` estimate when
you present the beat map, and again before the clip stage (the expensive one, roughly 70% of the
total). Re-rolls are normal: budget one or two per film. If a stage fails with 401/403 the key is
wrong; 402 or "insufficient balance" means the account needs credit, so stop and tell the person
rather than retrying.

## Not supported yet

This skill doesn't yet re-style a talking-head video, build a film around one photo of a person
or product, put a talking presenter on screen, or animate cut-out pieces one by one. If someone
asks for one of these, say so plainly and offer the closest thing it can do: a collage film on
their topic, using their photo as a reference image where that helps.
