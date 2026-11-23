# Footage handling: long clips, dark footage, photos, privacy

## Triage order (what worked for 15+ clips / ~7 min)
1. `analyze.py` (probe + sheets + metrics). Filename timestamps = shooting order/time of day; the map sorts by name.
2. View `overview.jpg`, then each `cNN.jpg`. Annotate `agent` blocks. Mark usable windows and anything with people/plates/signs.
3. For shortlisted windows: `peek.py <folder> <clip> --span a b --step 0.5` (coarse -> fine passes) and choose exact in-points. Prefer clean subjects, strong
   motion or light (flare, cloud over a ridge, tunnel exit); skip near-duplicates and dull grey frames.
4. Cut on action; frame-quantise (`plan.py validate --fix`).

## Very long clips (10+ min, multi-GB)
`analyze.py` samples keyframes only (`-skip_frame nokey`, seconds not minutes) and runs motion on 24 probe windows. Treat the clip as a menu of moments: view the
sheet(s), shortlist candidates, then `peek.py --span` around each. When the user names a section ("the split one"), find it by looking, state the time range
you chose, and keep THEIR order in the reel even if the source order differs.

## Dark / locked-off show footage
Contact sheets need a gamma lift (analysis applies 1.15; for night footage `peek` output may still be dark: lift more in your reading, never in the output).
Subject small in a mostly black frame: crop-zoom (`zoom:{factor,cx,cy}`); 4K portrait allows ~1.9x. Centre x on the brightness-weighted centroid of the lit area
(`peek.py --centroid`, bottom 28 % ignored), y on the subject's extent; manual centre where the lit area is not the subject (beams). Zoom 1.5 left 30-45 % empty black.

## Photos and exports
HEIC -> `sips` PNG (EXIF rotation stays; ffmpeg autorotates; `sips -g pixelWidth` reports unrotated size). Photo -> 9:16 with `crop {x,y,hf}`: choose x/y per photo to keep the
subject and drop foreground crowds, corner watermarks and "no photography" style signs; `push` 4-5 % keeps a still alive; photos are soft at the edges: 0.9-2 s each.
Messenger exports (`-WA` names): low-res, soft, bottom-corner watermark: crop it, use briefly, keep out of key moments.
If photos show a "photography prohibited" sign or were taken where it is restricted, ask the user before using them.

## Privacy
Personal info in footage = bystander/staff/passenger faces, readable plates, signage with names. Fix by moving the cut to a clean part, cropping, or dropping the shot
(not blurring). Distant tiny figures are acceptable. The user's own face is their call (mention when a shot shows it). `verify_output`-style OCR does not apply to
footage without on-screen text: say "sampled frames reviewed" and ask for a quick scrub before posting. Never upload footage to cloud APIs unless the user says so.
