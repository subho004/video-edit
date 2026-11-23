<div align="center">

# 🎬 video-edit

**Agent-driven video editing. Raw footage in, finished 4K reels and product videos out.**

Everything runs locally on your machine. One skill, any coding agent.

[![Last commit](https://img.shields.io/github/last-commit/subho004/video-edit?style=flat-square)](https://github.com/subho004/video-edit/commits/main)
[![Stars](https://img.shields.io/github/stars/subho004/video-edit?style=flat-square)](https://github.com/subho004/video-edit/stargazers)
[![Issues](https://img.shields.io/github/issues/subho004/video-edit?style=flat-square)](https://github.com/subho004/video-edit/issues)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](#contributing)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-6.1%2B-007808?style=flat-square&logo=ffmpeg&logoColor=white)
![Node](https://img.shields.io/badge/Node-18%2B-339933?style=flat-square&logo=nodedotjs&logoColor=white)
![Remotion](https://img.shields.io/badge/Remotion-optional-0B84F3?style=flat-square)
![Platform](https://img.shields.io/badge/macOS-Apple%20Silicon-000000?style=flat-square&logo=apple&logoColor=white)
![Runs locally](https://img.shields.io/badge/runs-100%25%20local-success?style=flat-square)

[How it works](#-how-it-works) ·
[Quick start](#-quick-start) ·
[Setup](#-setup) ·
[Scripts](#-scripts) ·
[Layout](#-project-layout) ·
[Contributing](#contributing)

</div>

---

## ✨ Features

- 📱 **Phone footage to Reel**: handles HDR 4K clips, photos and screen recordings.
- 🔍 **Real analysis**: frames, sharpness, motion, faces, duplicates and HDR detection, written to a JSON map.
- 🙋 **Human in the loop**: the agent asks you the decisions only you can make (goal, length, text, hero shot, privacy) before cutting.
- 🧾 **Validated edit plans**: a JSON plan (shots, speed, fx, crops, rationale) is checked and approved before rendering.
- 🎞️ **Best-quality export**: always 4K (2160x3840) at the highest source fps (up to 60) and a high bitrate. HDR is kept; an SDR copy only on request.
- 🛍️ **Product videos** via [Remotion](https://www.remotion.dev/).
- 💬 **Captions** from whisper.cpp, **beat sync** from librosa, **shot detection** from PySceneDetect.
- 🔒 **Originals are never modified or deleted.** All generated files go in `<footage folder>/_work/`.
- 🤖 **Agent-agnostic**: Claude Code, Codex, Cursor, Gemini CLI, opencode, Copilot and more.

## 🧭 How it works

```
<folder>/  raw clips + photos
   │
   ├─ analyze.py  →  _work/analysis/map.json + contact sheets
   │                 (frames, sharpness, motion, faces, duplicates, HDR)
   │
   ├─ agent reviews the sheets, annotates the map,
   │  and ASKS YOU the open decisions (goal, length, text, hero, privacy, ...)
   │
   ├─ plan.py     →  _work/plan.json  →  validate  →  you approve the cut
   │
   ├─ render.py   →  <Name>_Reel.mp4   (single HDR file, or Remotion for product videos)
   │
   └─ verify.py   →  tags, duration, silent audio, contact sheet of the real output
```

The behaviour lives in a single skill, [`.agents/skills/video-edit/`](.agents/skills/video-edit/SKILL.md).
`AGENTS.md` points to it and `CLAUDE.md` imports `AGENTS.md`.

## 🚀 Quick start

Once [set up](#-setup), open this repo in your coding agent and say:

```text
make a reel from the trip/ folder
```
```text
make a product video from demo.mp4
```

The agent follows `SKILL.md`: analyze, ask, plan, render, verify.

## 🛠 Setup

> macOS on Apple Silicon is the tested platform.

**1. System tools**
```bash
brew install ffmpeg whisper-cpp node   # ffmpeg 6.1+ (lut3d, prores_ks, libx264, hevc_videotoolbox), whisper.cpp, Node 18+
```

**2. Python** (3.10+)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # numpy, pillow, opencv, librosa, scenedetect
```

**3. Models** (git-ignored, stored in `models/`)
```bash
mkdir -p models
# faces (230 KB)
curl -L -o models/face_detection_yunet_2023mar.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
# captions (150 MB, optional)
curl -L -o models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```

**4. Remotion** (product videos, optional)
```bash
cd .agents/skills/video-edit/remotion && npm install
```
Companies need a paid Remotion licence; see the `remotion-license` skill.

**5. Third-party skills** (optional extras, installed into `.claude/skills/`)
```bash
npx skills add remotion-dev/skills --agent claude-code -y     # Remotion skills
npx skills add MakeMyClip/editor --agent claude-code -y       # transcript editing, silence removal, FCPXML export
npx ffmpeg-skill --project                                    # 42 ffmpeg tools
```
> ⚠️ These run with full agent permissions. Skim their `SKILL.md` first. `skills-lock.json` records versions.

**6. Check everything**
```bash
.venv/bin/python .agents/skills/video-edit/scripts/doctor.py
```
It prints what is missing and how to install it.

**7. Secrets**: copy `.env.sample` to `.env` only if a script needs a key (none do today). Never commit `.env`.

## 📜 Scripts

All scripts support `--help` and print JSON on stdout.

| Script | Job |
|---|---|
| `doctor.py` | Environment check and stale-path check for `SKILL.md` |
| `analyze.py <folder>` | `map.json` and contact sheets (cached, parallel) |
| `peek.py <folder> <clip> --span a b --step .5` | Fine-grained frames; `--centroid` for zoom centres |
| `plan.py draft / validate / snap / show` | Draft from the map, validate, beat-snap, print the shot table |
| `render.py plan.json [--preview]` | 4K HDR reel or Remotion product video; `--preview` gives a 1080p draft |
| `verify.py plan.json` | Check the rendered file(s) and write a contact sheet |
| `beats.py`, `scenes.py`, `captions.py` | librosa beat grid, PySceneDetect cuts, whisper.cpp word captions |

## 🗂 Project layout

```
.agents/skills/video-edit/   the skill: SKILL.md, scripts/, references/, templates/, remotion/
.claude/skills/video-edit    symlink to the skill (Claude Code reads .claude/skills)
<folder>/                    one per shoot; reels and the _work/ cache are written inside it
models/                      model files (git-ignored)
.env.sample                  secrets template
requirements.txt             Python dependencies
```

Claude Code reads `.claude/skills`; Codex, Cursor, Gemini, opencode and Copilot read `.agents/skills`.
On Windows, copy the folder instead of symlinking.

## Contributing

Issues and pull requests are welcome.

1. Fork the repo and create a branch: `git checkout -b feat/my-change`
2. Run `doctor.py` to confirm your environment is healthy.
3. Keep the always-on rules intact: 4K best-quality exports, originals untouched, outputs in `_work/`, secrets in `.env`.
4. Open a pull request describing what changed and why.

## 🙏 Acknowledgements

Built on [FFmpeg](https://ffmpeg.org/), [whisper.cpp](https://github.com/ggerganov/whisper.cpp), [Remotion](https://www.remotion.dev/), [OpenCV](https://opencv.org/), [librosa](https://librosa.org/) and [PySceneDetect](https://www.scenedetect.com/).
