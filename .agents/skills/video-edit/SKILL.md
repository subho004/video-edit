---
name: video-edit
description: >
  Use when the user wants to turn raw footage (phone clips, HDR 4K video, photos, a screen recording) into a finished
  video: an Instagram Reel / Short / TikTok from travel footage, a product or promo video, a captioned clip, a highlight
  cut, or "edit these videos", even if they never say "reel". Analyses every clip with Python (frames, sharpness, motion,
  faces, duplicates, HDR), writes a JSON map, asks the user for the decisions only they can make, drafts and validates a
  JSON edit plan, renders locally with ffmpeg (or Remotion for product videos) and verifies the output file.
  Not for: pure ffmpeg one-liners, audio-only work, or live-stream tooling.
license: MIT
compatibility: Needs ffmpeg 6.1+ (lut3d, prores_ks, libx264; hevc_videotoolbox for HDR on macOS), Python 3.10+, numpy, pillow, opencv. Optional librosa, scenedetect, whisper.cpp, Node (Remotion). Runs fully offline.
metadata:
  version: "1.0"
---

# video-edit

One skill, a fresh **plan per project**. Never edit by guessing: **analyse -> map.json -> ask -> plan.json -> render -> verify**.
Every script is a plain CLI (`--help`, JSON on stdout, no prompts). Paths are relative to the repo root; run Python with
`.venv/bin/python` (or any interpreter that has `requirements.txt` installed). `S=.agents/skills/video-edit/scripts`.

A project = one footage folder, e.g. `trip/`. Everything generated lives in `trip/_work/` (safe to delete); finished files go
in `trip/`. **Never modify or delete the user's original clips.**

## Rules that always apply
- **Ask, don't guess, at the decision gates below.** If you cannot ask interactively, state your assumption, proceed, and list it in the report.
- **Look at the frames.** Numbers are hints; the contact sheets are the evidence. Say "sampled frames reviewed", never "every frame".
- Keep the **original look** (no grade/filters) unless the user asks. HDR in -> a single HDR main file (no SDR copy unless the user asks: `output.sdr_fallback: true`); check its colour tags.
- **Exports are always 4K (2160x3840) at the highest source frame rate (max 60) and high bitrate** (HEVC ~55 Mb/s per 30 fps, x264 crf 14 SDR): the best quality the sources allow. Do not lower it unless asked; use `render.py --preview` (1080p draft) for quick review only. Low-res sources (photos, messenger clips) are upscaled: note it, do not hide it.
- Output is **silent** unless asked (music is added in the app). Music tracks are used for timing only.
- **Privacy**: avoid bystander faces, plates, name signs by choosing clean cut points; do not blur. Flag what you could not avoid.
- Approved shots (`approved: true`) are locked: change only what the user asked about, rebuild, re-verify, re-report.
- No place names, people's names or trip details in this skill, `AGENTS.md`, `CLAUDE.md` or `README.md`. Keep findings generic.
- If a delegated/parallel worker is available, use it for independent work (viewing many sheets, researching a style); otherwise do it inline.

## Workflow

### 0. Check the environment (once per machine/checkout)
`$S/doctor.py` -> if `ok:false`, install what the hints say (see `README.md`). Optional items only matter for the matching feature.

### 1. Brief (what is this video for?)
Infer what you can from the request and folder. **Ask the user** (batch the questions, offer defaults, one round) only for what is
unknown and changes the edit: goal/platform, target length, text line or none, hero shot / ending, anything to avoid, style
reference. Question bank and defaults: `references/decisions.md`. Record answers in `plan.json` -> `brief`/`decisions`.
Skip questions the user already answered in this conversation.

### 2. Analyse -> map.json
`$S/analyze.py <folder>` (cached; `--force` to redo; ~1-3 s per short clip). Produces `<folder>/_work/analysis/map.json`
(metrics, camera-motion segments, ranked candidate windows, flags, duplicates, `decisions_needed`) and contact sheets in
`_work/analysis/sheets/` (`overview.jpg` + one `cNN.jpg` per clip; "F" in a cell = face detected; HDR already tone-mapped).
Then **view the sheets** and fill each clip's `agent` block in map.json (subject, shot_type, use: hook|body|ending|skip, hero,
privacy, notes). Re-running analyze keeps those annotations. For a closer look use `$S/peek.py <folder> <clip> --span a b --step 0.5`.
Schema and how to read it: `references/analysis-map.md`. Long clips (>5 min): sample keyframes, ask which sections matter.

### 3. Decide with the user  (GATE 1)
Show a short table: what the footage contains, what you propose (structure, hook, ending, length), what you plan to leave out and why,
and the open decisions from `map.json -> decisions_needed` plus anything you noticed. Ask; wait for answers. Do not start rendering before this.

### 4. Plan -> plan.json
`$S/plan.py draft <folder> --target <sec>` writes a **draft** (best window per clip). Rewrite it by hand/LLM with the structure
from the brief: hook, rhythm, direction matching, hero/ending, speed/fx/crop choices, one-line `rationale` per shot. Optional:
`$S/plan.py snap plan.json --track song.mp3 --every 2` snaps cuts to the beat grid. Always `$S/plan.py validate plan.json`
(fix errors, read warnings) and `plan.py show` to print the table. Craft guidance: `references/reel-playbook.md`
(or `references/product-playbook.md`). Pick a story structure and sequence blocks from `references/cinematic-sequences.md`
and state the choice in the plan's rationale. Field reference: `references/plan-schema.md`.

### 5. Approve the cut  (GATE 2)
Show the shot table (time | shot | source | why) and the left-out list. Ask for approval or edits. Set `approved: true` on approved shots.

### 6. Render
`$S/render.py <folder>/_work/plan.json` -> **4K** `<folder>/<Name>_Reel.mp4` (HDR when any source is HDR, else SDR) at the highest source fps (max 60). Optional `--preview` first: a fast 1080p draft `<Name>_Reel_preview.mp4` (HDR only) to check the cut. 4K cache is ~50 MB per second of footage in `_work/segments`; a 30 s reel takes a few minutes. Segments are cached; only changed shots re-render. `--only s3,s4` renders a subset for a quick test.
Product videos: `type: "product"` renders the Remotion template (see `references/product-playbook.md`).

### 7. Verify the output file  (not the plan)
`$S/verify.py <folder>/_work/plan.json` -> tags of both files, duration, size/fps, silent audio, blank frames, and a contact sheet
of the first/last frame of every shot at `_work/verify/<Name>_check.jpg`. **Open that sheet and look** (cuts, crops, text, watermarks,
strangers). `not_measured` = fail. Fix and re-run until `ok:true`.

### 8. Report and iterate
Report: shot table, what was left out, what was checked (and what was not), the assumptions you made, and one-line alternatives.
Ask the user to scrub before posting. For feedback, edit only `plan.json`, re-validate, re-render, re-verify. When the user states
a new durable preference, add one generic line to `references/learned-preferences.md`.

## Pick the right reference (load only when needed)
| Situation | Read |
|---|---|
| Building the shot list for a reel, pacing, hook, text, walking footage, trends | `references/reel-playbook.md` |
| Choosing a story structure, ordering clips, match cuts, J/L-cuts, ramps, beat/sound/caption timing | `references/cinematic-sequences.md` |
| Product / promo / explainer / talking or demo video, captions | `references/product-playbook.md` |
| Which questions to ask and what defaults to propose | `references/decisions.md` |
| map.json fields, annotating clips, interpreting flags | `references/analysis-map.md` |
| plan.json fields, fx/ramp/crop/zoom/push, validation rules | `references/plan-schema.md` |
| HDR/SDR/colour, LUTs, text in HDR, encode settings, ffmpeg build limits | `references/color-and-encode.md` |
| Long clips, dark footage, HEIC/photos, privacy, triage tricks | `references/footage-handling.md` |
| Something failed or looks wrong | `references/troubleshooting.md` |
| Trend styles and how automatable each is | `references/styles.md` |
| Sources behind these choices | `references/research-notes.md` |
| Preferences learned from past users (append new ones) | `references/learned-preferences.md` |

## Gotchas (short list; details in troubleshooting.md)
- The PQ tag leaks into the SDR file unless the chain ends with `setparams` (render.py does this; ffprobe the tags, ffmpeg frame dumps ignore them).
- Python `hash()` is randomised: cache keys use md5 (`vlib.md5`). Do not change that.
- `-ss` before `-i` for fast seek; for B-frame-heavy clips peek with `--span`, not many single seeks.
- HEIC: converted with `sips` (macOS). Elsewhere convert first. WhatsApp-style exports are soft and carry a corner watermark: crop it.
- This ffmpeg build may lack `zscale`, `drawtext`, `libx265`; the scripts avoid them (PIL text overlay, LUT tone-mapping).
- Do not render into the footage folder under names the analyser would pick up as clips: analysers skip `*_Reel*` files.
