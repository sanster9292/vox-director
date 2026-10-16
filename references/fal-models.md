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

## Defaults (tested end to end)

| Job | Endpoint | Price seen | Notes |
|---|---|---|---|
| Keyframe | `fal-ai/nano-banana-2` | $0.08 / image (1K) | renders headline text well; `aspect_ratio`, `resolution` 0.5K/1K/2K/4K |
| Keyframe with real refs, 2K pass, fixes | `fal-ai/nano-banana-2/edit` | ~$0.08–0.12 / image | `image_urls` accepts public URLs or `data:` URIs |
| Animate | `minimax/h3-max-turbo/image-to-video` | 480P $0.025/s · 768P $0.04/s · **1080P $0.08/s** (list) | no aspect field: output follows the input image; `duration` 1–15 s |
| Narration | `google/gemini-3.8-flash-tts` | $0.045 / 1000 chars | text in `prompt`; delivery in `style_instructions`; handles code-switched Urdu/Hindi + English |
| Music | `fal-ai/minimax-music/v2.6` | $0.15 / track | `is_instrumental: true`; returns ~100 s, assemble trims and fades it |

A 30 s, 6-beat 9:16 film at the defaults costs roughly **$3–4**: 6 keyframes ($0.48), 6 2K
passes (~$0.70), 30 s of 1080P video (~$2.40), narration (~$0.03), music ($0.15). Re-rolls add to that.

## Alternatives worth knowing

| Want | Endpoint | Why / caveat |
|---|---|---|
| Cheapest motion | H3 Max Turbo at `480P` | faces go soft and "AI-looking"; fine for drafts, not for people-heavy films |
| Best H3 motion and faces | `minimax/h3-max/image-to-video` | ~2× Turbo's price at each resolution |
| Text-stable animation | `google/gemini-omni-flash/image-to-video` | ~$0.13/s at 720p; params `aspect_ratio` 16:9/9:16 only, `duration` 3–10; refuses recognisable celebrities/logos |
| Real people / celebrities | Kling (`kling-video` image-to-video endpoints) | the original vox-director notes Omni and Seedance block real celebrities; Kling allows them |
| Cheap English TTS | `xai/tts/v1` | $0.015/1000 chars, text field is `text`, no Urdu (has hi, bn, ar…) |

To switch models, change `beats.json` only (`video.model` + `video.params`, `tts.model` +
`tts.text_field` + `tts.params`). The scripts pass `params` through unchanged, so check the
model's input fields first: a wrong field name is silently ignored by some models.

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
