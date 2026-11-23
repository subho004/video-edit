# Product / promo / demo videos

Read after the Brief gate. Same loop as reels (analyse -> ask -> plan -> render -> verify); the render path differs.

## Pick the route
| Video | Route |
|---|---|
| Hero footage + animated hook/offer/captions (teaser, launch, ad) | `type: "product"` -> Remotion `ProductReel` template (`remotion/`) |
| Montage of several product clips with plain cuts | `type: "reel"` with product clips (ffmpeg), maybe `fx`, `ramp`, one text line |
| Talking head / demo with speech | transcript-driven: `captions.py` (whisper.cpp) -> Remotion captions, or the installed `editor` skill for silence/retake removal |
| Need a human-editable timeline at the end | `editor` skill (FCPXML/XML export) |

## Brief questions specific to products (ask once)
Product name and the ONE claim; audience; offer/date/CTA wording (the user writes it, never invent claims, prices or dates); hero shot; brand colours
and font if any; length (10-20 s teaser, 20-45 s demo); captions needed (is there speech?); platform safe zones.

## Remotion template (`remotion/src/ProductReel.tsx`)
Composition `ProductReel` authored at 1080x1920, rendered at `--scale=2` = **4K 2160x3840**, fps = the clip's fps (<= 60), `--crf=12`: slow-then-fast blurred-zoom reveal of the clip, hook line (spring pop, fades by 2.8 s), optional
word-by-word captions with the current word highlighted, offer card in the last 2.5 s, 0.5 s fade. Text stays inside the safe zones
(top 250 / bottom 350 px). Props: `hook`, `offer`, `clip` (file in `remotion/public/`), `captionsFile`, `durationSec`, `fps`.
`plan.json`: `"type":"product","product":{"clip":"demo.mp4","hook":"...","offer":"...","captions":true,"duration":12}` then `render.py`.
First time: `cd .agents/skills/video-edit/remotion && npm install` (first render downloads a headless Chrome; the first still may time out once, retry).
Customise by editing the TSX (see the installed `remotion-*` skills: best-practices, captions, render). Licence: Remotion is paid for companies; check `remotion-license`.

## Craft
- Hook in the first 1-3 s: what it is or the payoff, as text and picture. Show the product within 2 s.
- One message per video; a single claim; end with the offer/CTA card the user approved.
- Clean, steady, well-exposed hero shots: use `metrics` + sheets; avoid hands/faces intruding unless intended; check text legibility and reflections/blown highlights.
- Reveal formats (tear-through, wipe, whip-zoom) are easy; subject cut-outs / text-behind-subject need per-frame mattes: prototype first, check flicker, expect manual review.
- Captions: burn in (most feeds start muted) AND keep audio good. Whisper word timing jitters ~0.3 s: cut on segment boundaries.
- Grain/glitch/dreamy looks are allowed for brand pieces only when asked (they break the original-look rule for travel).
- Verify the rendered MP4 (`verify.py`), then eyeball a frame at the hook, the reveal, the captions and the CTA.
