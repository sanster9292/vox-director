# Changes from Alisa0808/vox-director

This fork rebuilds [Alisa0808/vox-director](https://github.com/Alisa0808/vox-director) (Atlas Cloud
edition) on fal.ai. The changes are below, grouped by the commit that made them on the
`fal-edition` branch, each with the reason for it.

## 1. Port to fal.ai

| Change | Why |
|---|---|
| Replaced the Atlas Cloud pipeline with a fal.ai one: `SKILL.md`, `scripts/` (`falq.py` queue client, `keyframes`, `hires`, `clips`, `audio`, `captions`, `assemble`, `refs`, `review`, `set_fal_key.sh`), `references/fal-models.md` and a Faisalabad example beat map | The pipeline had to run on a fal.ai key. fal also hosts the open-weights image and video models this edition prefers. |
| Added `hires.py` (2K re-render of each approved keyframe, plus one-instruction `--fix` edits) | At 1K a face is only a few dozen pixels tall before animation, so people come out blurry and "AI-looking" in the final film. |
| Added `refs.py` (Wikimedia Commons landmark photos with automatic `CREDITS.md`) | Without a reference photo the image model invents a plausible but wrong building. |
| Added `review.py` contact sheets (keyframes, clips, title-area crops, final) | The agent can't watch video, so it checks a still sheet before each paid step. |
| Captions via a bundled Swift renderer on macOS, Pillow elsewhere | Mixed-script (Urdu + English) captions need proper shaping and bidi, which CoreText handles. ffmpeg's text filters aren't used because many builds lack libfreetype/libass. |
| Removed `SKILL.zh.md`, `README.zh.md`, `AGENTS.md`, `llms.txt`, `vox-director.skill`, the Atlas-only scripts (`atlas_cloud`, `provider`, `host*`, `aroll*`, `croll_keyframes`, `motion`, `kenburns`, `style_bakeoff`, …), their references (`host-mode`, `local-engine`, `models-and-gotchas`, `voices`) and examples | They describe Atlas endpoints, keys and features this edition doesn't have, so keeping them would mislead both people and agents. `README.zh.md` and `AGENTS.md` weren't on the original removal list but were Atlas-only in the same way. |
| Kept `LICENSE`, `assets/` (untouched) and `.gitignore` | The MIT licence and its copyright notice must stay. The showcase films are the original author's. |
| `package.json`: name `vox-director-fal`, fal.ai description, this fork's URL, upstream credited under `contributors` | So the package metadata says what this edition is and where it came from. |

## 2. No built-in models + schema-aware requests

| Change | Why |
|---|---|
| Removed every hard-coded model default from `keyframes.py`, `hires.py`, `clips.py`, `audio.py` | Model choice is a per-project decision about licence, price and quality. A silent default skipped that decision. |
| `project.need()` stops a stage with a message naming the missing `beats.json` field | A missing model should be an obvious error, not a silent fallback. |
| `falq.fit()` reshapes one neutral payload to each endpoint's OpenAPI input schema (aspect + resolution → `image_size`, `image_urls` ↔ `image_url`, `prompt` ↔ `text`, durations snapped to the model's choices). Unknown fields are dropped with a note, and schemas are cached for a week | Models name the same inputs differently, and some silently ignore unknown fields. With `fit()`, switching models only takes a `beats.json` edit. |
| `clips.py` handles string durations (`"5s"`) in cost estimates | Some video models take duration as a string, and `fit()` passes that through. |
| `keyframes.py` keeps `data:` URIs out of the log for both `image_url` and `image_urls` | After `fit()` a single-reference model gets `image_url`, which would otherwise log a multi-MB base64 blob. |
| `audio.py` reuses `audio/music.mp3` if present; `music.model` becomes optional then | People often have a track they want to use, and generating one anyway would cost money for nothing. |
| `SKILL.md` + `references/fal-models.md`: selection rules (the person's pick, then open weights first), the open-weights image model table, and the old defaults relabelled "tested combination (closed)" | The rules the code now relies on have to be written down where the agent reads them. |

## 3. Single-skill wording

| Change | Why |
|---|---|
| "Not in this edition" → "Not supported yet", which now offers the closest thing the skill can do | The repo holds one skill, so pointing at a sibling Atlas edition sent people somewhere that isn't here. |
| Dropped "(fal edition)" from the title, "prefer this over an Atlas Cloud skill" from the description, and "the original vox-director notes" from the Kling row | Same reason: there's no second skill to compare against. |

## 4. Vox-only trigger, open source then cheapest, draft pass, real-place references

| Change | Why |
|---|---|
| The skill description now triggers **only** on requests for a Vox-style video | The old one also claimed generic collage and motion-graphics requests, which should go to other tools. |
| Model rule 3: among open models that pass a one-keyframe test, pick the cheapest at the cheapest settings that still look right; drafts use the cheapest open model outright | Once licence is settled, price is the next deciding factor. |
| `--draft` on every stage (`project.py`): works in `<project>/draft/` with links to `beats.json` and `references/`, applies the `beats.json` `"draft"` overrides (default 480P video) | Lets people try ideas cheaply before paying for the final film. |
| `hires.py`: skips the 2K pass in a draft; outside a draft it starts from the approved draft keyframes ("lock in") | A 2K pass isn't worth paying for on a draft, and locking in keeps the layout the person approved. |
| `refs.py`: `add` for the person's own photos first; web search only after they agree, in order Google Maps place photos → Pexels → Commons photos geotagged near the place → Commons keyword search. Every source writes a `CREDITS.md` line, and people are never searched for | Commons alone often has nothing for shops, restaurants or streets. The person's own photos are the most accurate and need no licence check. Searching for photos of private people raises consent issues. |
| `set_key.sh <item>` stores any key in the Keychain; `set_fal_key.sh` stays as a wrapper; `falq.secret()` reads env or Keychain per key | The new photo sources need their own keys, and the old instructions should keep working. |

## 5. Docs

| Change | Why |
|---|---|
| `docs/annotated.html`: the skill with margin notes on each design decision | Makes the reasoning behind each rule easy to review. |
| Rewrote `README.md` (what it is, install, quick start, draft → final, model rules, keys, credit) | The original README described the Atlas edition. |
| This `CHANGES.md` | So every difference from upstream is listed along with its reason. |

## Credits

- Original skill: **[Alisa0808/vox-director](https://github.com/Alisa0808/vox-director)** (MIT, © 2026 Alisa Qian).
- fal.ai edition: **[sanster9292](https://github.com/sanster9292)**.
- AI assistance, as recorded on every commit:

```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
AI-Model: Claude Opus 5.5 (claude-opus-5-5), design + implementation session
AI-Effort: not reported by the session (default)
AI-Tokens: ~21.2M processed (~20.6M cached re-reads, ~378K cache writes, ~156K output; ~3.6M input-equivalent)
AI-Git-Model: Claude Opus 5.5 (claude-opus-5-5), history rebuild + docs + push session
AI-Git-Effort: not reported by the session (default)
AI-Git-Tokens: ~0.15M context at the final commit (estimate; exact metering not visible to the session)
```
