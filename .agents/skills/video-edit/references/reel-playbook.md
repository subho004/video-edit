# Reel playbook (travel / lifestyle footage -> 9:16)

## Defaults that users of this skill kept asking for (follow unless told otherwise)
- **Original look.** No grade, no saturation/contrast boost, no filters; only cuts, speed, order and (optionally) one text line. An early
  version with a tone-map plus extra punch was rejected as "exposed / too much filter". Deliver the footage's own colour.
- **One text line for the whole video**, or none. Big, upper area, constant (fade in 0.3-0.4 s, out with the end fade), POV-style
  ("POV: you escape to the hills"). Broad theme, not one subject. No per-shot labels, no call-to-action. "No captions inside the video" is valid.
- **Silent output.** Drop all original audio (wind, voices, ride noise); keep a silent AAC track. Music is added in the app.
- **Pace**: fast opening montage (~2-2.5 s/shot, 1.5-2x for road/ride shots), then a calmer "experience" section (3-3.5 s, or one continuous POV take).
  Hook = the strongest or most unusual first frame, inside 1.5-3 s. Photos as flash bursts (0.9-1.6 s each) work as rhythm.
- **Walking footage**: alternate back shots and forward-POV shots; keep the same direction of travel and subject placement across each cut;
  1x speed only (sped-up people look comedic); end on a wide "walking away" shot + 0.5 s fade. Never end on, or spend a shot on, the subject
  turning to the camera unless asked.
- **Don't centre the reel on one subject** (one vehicle, one monument) unless the user wants that; show the place.
- Keep approved shots unchanged; "replace with a moving clip" = pick a high-motion shot (rushing forest, curves), not a static one.
- Edit order: cut length -> hook -> cut on rhythm -> text -> music last.

## Structure template (adapt to the footage)
1. Hook (0-3 s): the single strongest frame/motion. 2. Fast montage of scenery/transport/details (varied: wide, medium, detail). 3. Experience section:
longer shots, a continuous walk or ride. 4. Ending: calm wide shot, fade out. Vary shot types; drop near-duplicates; never two similar shots in a row.
Length: 7-15 s single highlight, 15-45 s mini-vlog, 30-60 s common. Safe zones on 1080x1920: keep text and key subjects out of the top ~250 px and bottom ~350 px.

## Making the choices with the map
- Start from `candidates[0]` of each clip, then look at the sheets; prefer sharp, steady, well-exposed, clean-subject windows, strong motion or light.
- `camera_segments` tell you the shot type: `moving` = walk/ride, `pan_*` = scenery sweep, `static` = locked/detail. Use pan direction to chain
  shots (right-pan then right-pan) and to align walking directions.
- Avoid windows with `contains_cut`, `face_in_frame`, `shaky`, `exposure_issue`. If a clip is long, take the best 2-4 s, not the whole.
- Beat-synced cut: `plan.py snap --track t.mp3 --every 2` (every 2nd/4th beat for travel; min gap 0.35 s). Cutting on every beat feels frantic.

## Trendy techniques the plan supports (see `styles.md` for the full automation matrix)
`fx:"flash"` / `fx:"zoom"` on beat cuts; `ramp` for speed ramps and slow-mo hits; `push` on photos; `zoom` for punch-ins (keep <= 1.2x on camera
changes); beat snapping; photo-dump flashes; POV text hook. Film grain, glitch and "dreamy" looks conflict with the original-look rule: only
on request and only for product/brand pieces.

## Iteration loop that works
Propose a shot table -> build -> report table, left-outs, what was checked -> user gives small edits ("swap the last two", "add the cloudy
roads") -> change only `plan.json`, rebuild, re-verify, re-report. Put alternatives in one line at the end instead of asking up front.
