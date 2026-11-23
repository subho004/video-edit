# Trend styles and how automatable they are (2026, from marketing blogs: directional, check current Reels)

| Style | Automation | How |
|---|---|---|
| Hook in first 1-3 s + one POV text line | easy | plan `text`, strongest frame first, text in safe zone |
| Beat-synced cuts / location-jump montage | easy-medium | `beats.py`, `plan.py snap --every 2|4`; the hard part is clean cut points + direction matching (agent + eyes) |
| Photo-dump flash cuts | easy | stills at 0.9-1.6 s, `push`, burst of 3 |
| Whip-zoom / flash transitions | medium | `fx: zoom|flash` (2-4 frames), on beats only |
| Speed ramps / slow-mo hit | medium | `ramp: [a, b, s]` around the action, short |
| Split screen / before-after wipe | easy | ffmpeg hstack/vstack/xfade or Remotion clip-path (not in render.py yet) |
| Kinetic / word-by-word captions | medium | `captions.py` -> Remotion template; needs speech |
| Product reveal / tear-through (6-12 s) | medium | Remotion `ProductReel` |
| Text behind subject / freeze-frame cut-out | hard | per-frame mattes (rembg / SAM2-class); flicker risk; prototype + human check |
| Glitch / RGB-split / shake | medium | `rgbashift`, animate on beats; sparing; conflicts with original-look rule for travel |
| Film grain / dreamy | easy | only for brand pieces on request |
| Match cuts, hyperlapse, loop endings | hard | similarity detection / stabilised source; agent suggests, human approves |
Needs a human: hero shot and hook choice, clean-cut judgement, matte quality, music choice (trending audio is picked in the app), final privacy scrub.
