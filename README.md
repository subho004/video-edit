# video-edit

Agent-driven video editing: turn raw footage (phone clips, HDR 4K, photos) into Instagram Reels, product videos and captioned clips.
Everything runs locally. The behaviour lives in ONE skill, `.agents/skills/video-edit/`, that any coding agent can follow
(Claude Code, Codex, Cursor, Gemini CLI, opencode, Copilot, ...). `AGENTS.md` points to it; `CLAUDE.md` imports `AGENTS.md`.

## How it works (per project folder)
```
<folder>/ raw clips + photos
   analyze.py   -> _work/analysis/map.json + contact sheets     (Python: frames, sharpness, motion, faces, duplicates, HDR)
   agent looks at the sheets, annotates the map, ASKS YOU the open decisions (goal, length, text, hero, privacy, ...)
   plan.py      -> _work/plan.json (shots, speed, fx, crops, rationale) -> validate -> you approve the cut
   render.py    -> <Name>_Reel.mp4 (single HDR file)              (or Remotion for product videos)
   verify.py    -> tags, duration, silent audio, contact sheet of the real output
```
Just tell your agent: "make a reel from the `trip/` folder" (or "product video from `demo.mp4`"). It follows `SKILL.md`.

## Setup from scratch (macOS, Apple Silicon)
**1. System tools**
```bash
brew install ffmpeg whisper-cpp node        # ffmpeg 6.1+ (lut3d, prores_ks, libx264, hevc_videotoolbox); whisper.cpp; Node 18+
```
**2. Python**
```bash
python3 -m venv .venv                       # Python 3.10+
.venv/bin/pip install -r requirements.txt   # numpy, pillow, opencv, librosa (beats), scenedetect (shot detection)
```
**3. Models** (git-ignored, in `models/`)
```bash
mkdir -p models
curl -L -o models/face_detection_yunet_2023mar.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx   # faces (230 KB)
curl -L -o models/ggml-base.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin                                                 # captions (150 MB, optional)
```
**4. Remotion (product videos, optional)**: `cd .agents/skills/video-edit/remotion && npm install` (paid licence for companies: see the `remotion-license` skill).
**5. Third-party skills (optional extras, installed into `.claude/skills/`)**
```bash
npx skills add remotion-dev/skills --agent claude-code -y     # Remotion skills
npx skills add MakeMyClip/editor --agent claude-code -y       # transcript editing, silence removal, FCPXML export
npx ffmpeg-skill --project                                    # 42 ffmpeg tools
```
They run with full agent permissions: skim their `SKILL.md` first. `skills-lock.json` records versions.
**6. Check everything**: `.venv/bin/python .agents/skills/video-edit/scripts/doctor.py` (prints what is missing and how to install it).
**7. Secrets**: copy `.env.sample` to `.env` only if a script needs a key (none do today).

## Layout
- `.agents/skills/video-edit/` the skill: `SKILL.md`, `scripts/`, `references/`, `templates/`, `remotion/`. `.claude/skills/video-edit` is a symlink to it
  (Claude Code reads `.claude/skills`; Codex, Cursor, Gemini, opencode, Copilot read `.agents/skills`. On Windows copy instead of symlinking).
- `<folder>/` one per shoot; reels and the cache `_work/` are written inside it. Originals are never touched.
- `models/` model files; `.env.sample` secrets template; `requirements.txt` Python deps.

## Scripts (all `--help`, JSON on stdout)
| script | job |
|---|---|
| `doctor.py` | environment check + stale-path check for SKILL.md |
| `analyze.py <folder>` | map.json + contact sheets (cached, parallel) |
| `peek.py <folder> <clip> --span a b --step .5` | fine frames; `--centroid` for zoom centres |
| `plan.py draft / validate / snap / show` | draft from the map, validate, beat-snap, print the shot table |
| `render.py plan.json [--preview]` | 4K (2160x3840), highest source fps (<= 60), high bitrate: HDR reel (SDR copy only on request), or Remotion product video; `--preview` = 1080p draft |
| `verify.py plan.json` | check the rendered file(s), write a contact sheet |
| `beats.py`, `scenes.py`, `captions.py` | librosa beat grid, PySceneDetect cuts, whisper.cpp word captions |
