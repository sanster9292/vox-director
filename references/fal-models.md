# fal models, prices and gotchas

Read this before choosing models, before debugging a failure, or when someone asks what a
run will cost. Everything here was checked against fal's live catalog in October 2026, but fal
changes fast, so **verify model IDs and prices before a run**:

```bash
# search the catalog (needs the key)
curl -s -G https://api.fal.ai/v1/models --data-urlencode "q=image to video" -H "Authorization: Key $FAL_KEY"
# a model's input fields
curl -s "https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=<endpoint>"
# list price (base tier only; see "price traps" below)
curl -s -G https://api.fal.ai/v1/models/pricing --data-urlencode "endpoint_id=<endpoint>" -H "Authorization: Key $FAL_KEY"
```
Every stage script also takes `--dry-run`, which prints the exact jobs and a cost estimate
without submitting anything. Use it and show the user the estimate before spending.

## Choosing models (nothing is defaulted)

The scripts have no built-in models. Every project names its own in `beats.json`
(`image.model`, `image.edit_model`, `video.model`, `tts.model`, and `music.model` only if you
generate music), and a stage stops with a clear message if its model is missing. Pick them when
you write the beat map and show them to the person with the cost estimate at the approval gate:

1. **The person's choice wins.**
2. **Open source first, whatever the country of origin:** permissive license (Apache 2.0 / MIT)
   → open weights under a non-commercial self-host license (outputs still usable through fal)
   → closed only if no open model does the job.
3. **Then optimise for price.** Among the open models that pass the one-keyframe test, pick the
   cheapest, at the cheapest settings that still look right (resolution, duration tier). For a
   draft pass, pick the cheapest open model outright.
4. **Check the license on the day** for non-commercial clauses.
5. **Check the inputs** with the schema URL above (reference-image field, sizes, durations).
   `falq.fit()` reshapes the payload to each model's own fields automatically (aspect ratio to
   `image_size`, `image_urls` to `image_url`, `prompt` to `text`, durations snapped to what the
   model offers) and prints a note for anything it drops.
6. **Test one keyframe** before a full run. Open image models can trail closed ones on long
   multi-line headlines; keep headlines short or re-roll.

### Open-weights image models on fal (checked 15 Oct 2026)

| Use | Endpoint | License | Reference images | Price seen |
|---|---|---|---|---|
| Edit with refs, 2K pass, fixes | `fal-ai/qwen-image-edit-2511` | Apache 2.0 | yes (`image_urls` list) | $0.03 / MP |
| Cheap drafts, edit with refs | `fal-ai/flux-2/klein/4b/edit` (t2i: `fal-ai/flux-2/klein/4b`) | Apache 2.0 | multi-reference | $0.009 / MP |
| Edit with refs, higher quality | `fal-ai/flux-2/klein/9b` | FLUX Non-Commercial (outputs fine via fal; self-hosting needs a BFL license) | multi-reference | check page |
| Text-to-image keyframes | `fal-ai/qwen-image` | Apache 2.0 | none | check page |
| Fast text-to-image | `fal-ai/z-image/turbo` | Apache 2.0 | single init image only | check page |

Suggested open roster: `image.model` = Qwen-Image, `image.edit_model` = Qwen-Image-Edit-2511.
For a draft pass, FLUX.2 [klein] 4B is the cheapest open option for both
(`"draft": {"image": {"model": "fal-ai/flux-2/klein/4b", "edit_model": "fal-ai/flux-2/klein/4b/edit"}}`). Qwen and FLUX take `image_size`, not
`aspect_ratio` + `resolution`; `fit()` converts (2K → a 2048 px long side).

### Tested combination (October 2026, closed image models)

The film in `examples/` was made with these. Use them when an open model fails the one-keyframe test.

| Job | Endpoint | Price seen | Notes |
|---|---|---|---|
| Keyframe | `fal-ai/nano-banana-2` | $0.08 / image (1K) | renders headline text well; `aspect_ratio`, `resolution` 0.5K/1K/2K/4K |
| Keyframe with real refs, 2K pass, fixes | `fal-ai/nano-banana-2/edit` | ~$0.08–0.12 / image | `image_urls` accepts public URLs or `data:` URIs |
| Animate | `minimax/h3-max-turbo/image-to-video` | 480P $0.025/s · 768P $0.04/s · **1080P $0.08/s** (list) | no aspect field: output follows the input image; `duration` 1–15 s |
| Narration | `google/gemini-3.8-flash-tts` | $0.045 / 1000 chars | text in `prompt`; delivery in `style_instructions`; handles code-switched Urdu/Hindi + English |
| Music | `fal-ai/minimax-music/v2.6` | $0.15 / track | `is_instrumental: true`; returns ~100 s, assemble trims and fades it |

A 30 s, 6-beat 9:16 film with this combination costs roughly **$3–4**: 6 keyframes ($0.48), 6 2K
passes (~$0.70), 30 s of 1080P video (~$2.40), narration (~$0.03), music ($0.15). Re-rolls add to that.

## Alternatives worth knowing

| Want | Endpoint | Why / caveat |
|---|---|---|
| Cheapest motion | H3 Max Turbo at `480P` | faces go soft and "AI-looking"; fine for drafts, not for people-heavy films |
| Best H3 motion and faces | `minimax/h3-max/image-to-video` | ~2× Turbo's price at each resolution |
| Text-stable animation | `google/gemini-omni-flash/image-to-video` | ~$0.13/s at 720p; params `aspect_ratio` 16:9/9:16 only, `duration` 3–10; refuses recognisable celebrities/logos |
| Real people / celebrities | Kling (`kling-video` image-to-video endpoints) | Omni and Seedance have refused real celebrities in past runs; Kling allows them |
| Cheap English TTS | `xai/tts/v1` | $0.015/1000 chars, text field is `text`, no Urdu (has hi, bn, ar…) |

To switch models, change `beats.json` only (`video.model` + `video.params`, `tts.model` +
`tts.params`). `fit()` renames common fields to the model's own and drops the rest with a note,
so read those notes on the first run with a new model. If the schema can't be fetched, the
payload goes out unchanged.

## Price traps

- **The pricing API returns the base tier.** H3 Max Turbo reports $0.015/s, which is the 480P promo
  price; 1080P costs several times more. The `--dry-run` estimate uses that base number, so read
  the model page (`https://fal.ai/models/<endpoint>`) for resolution tiers.
- Gemini Omni reports `unit_price: 1, unit: units` (token billing); its page says ~$0.13/s at 720p.
- Launch promos expire (H3's 40% discount ended 15 Oct 2026). Quote ranges, not exact numbers.

## Gotchas (each one cost a re-run)

1. **SSL on macOS python.org builds:** `CERTIFICATE_VERIFY_FAILED`. `falq.py` falls back to
   `/etc/ssl/cert.pem` automatically; to fix it for good run
   `/Applications/Python 3.x/Install Certificates.command`.
2. **ffmpeg without drawtext/libass** is common (Homebrew's minimal builds). Captions are
   rendered to PNG (`captions.py`) and overlaid, never drawn by ffmpeg.
3. **Mixed-script captions** (Urdu + English in one line) come out in a confusing order when a
   line wraps, even with correct bidi. For code-switched narration, caption in Roman Urdu /
   Hinglish (Latin script) while the voice speaks the native script. That's also how most
   Pakistani and Indian social video is captioned.
4. **Headlines get covered by moving elements:** smoke, kites, petals and fabric drift over the
   banner. Keep motion verbs for the lower part of the frame, say so in `motion`, and check
   `review.py <project> title <beat>` on every clip.
5. **Spires and tall objects poke into the banner** in keyframes ("TO" read as "TQ"). Fix one
   keyframe with `hires.py --ids N --fix "..."` (~$0.12), not a full re-roll.
6. **Stray quotation marks around headlines** happen now and then; re-roll that one keyframe.
7. **Clip length ≠ narration length.** Generate narration per beat; `assemble.py` slows a clip to
   fit a longer line (setpts), never freezes it.
8. **Video models add their own soundtrack.** `assemble.py` never uses clip audio; only the
   narration and music are mixed.
