#!/usr/bin/env python
"""Environment check for the video-edit skill. Prints JSON {ok, required, optional}; exit 1 if a REQUIRED item is missing.
  doctor.py
Each failing item carries an install hint. Run it first in a new checkout or on a new machine."""
import json, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vlib import REPO, SKILL


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except Exception as e:
        return None


def item(name, ok, hint="", detail=""):
    return dict(name=name, ok=bool(ok), hint="" if ok else hint, detail=detail)


def main():
    req, opt = [], []
    ff = shutil.which("ffmpeg")
    req.append(item("ffmpeg", ff, "brew install ffmpeg"))
    if ff:
        enc = sh(["ffmpeg", "-hide_banner", "-encoders"]).stdout
        filt = sh(["ffmpeg", "-hide_banner", "-filters"]).stdout
        for e in ("prores_ks", "libx264", "hevc_videotoolbox"):
            req.append(item(f"ffmpeg encoder {e}", e in enc, "install an ffmpeg build with this encoder (macOS: brew install ffmpeg; hevc_videotoolbox is macOS-only)"))
        for f in ("lut3d", "overlay", "fade", "setparams", "crop", "scale"):
            req.append(item(f"ffmpeg filter {f}", f" {f} " in filt, "ffmpeg build is missing a core filter"))
        opt.append(item("ffmpeg zscale (not needed: LUTs are used instead)", " zscale " in filt, "optional"))
    req.append(item("ffprobe", shutil.which("ffprobe"), "ships with ffmpeg"))
    req.append(item("python >= 3.10", sys.version_info >= (3, 10), "install Python 3.10+", sys.version.split()[0]))
    for mod, pip in (("numpy", "numpy"), ("PIL", "pillow"), ("cv2", "opencv-python-headless"), ("librosa", "librosa"), ("scenedetect", "scenedetect[opencv-headless]")):
        try:
            __import__(mod); ok = True
        except Exception:
            ok = False
        (req if mod in ("numpy", "PIL", "cv2") else opt).append(item(f"python module {mod}", ok, f"pip install {pip}  (or: pip install -r requirements.txt)"))
    opt.append(item("sips (HEIC conversion, macOS)", shutil.which("sips"), "on non-macOS convert HEIC with ImageMagick/libheif first"))
    opt.append(item("face model (models/face_detection_yunet_2023mar.onnx)", (REPO / "models" / "face_detection_yunet_2023mar.onnx").exists(),
                    "curl -L -o models/face_detection_yunet_2023mar.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"))
    opt.append(item("whisper-cli (captions)", shutil.which("whisper-cli"), "brew install whisper-cpp"))
    opt.append(item("whisper model (models/ggml-base.en.bin)", (REPO / "models" / "ggml-base.en.bin").exists(),
                    "curl -L -o models/ggml-base.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"))
    opt.append(item("node + npm (product videos)", shutil.which("node") and shutil.which("npm"), "brew install node"))
    opt.append(item("remotion deps (skill remotion/node_modules)", (SKILL / "remotion" / "node_modules").exists(), "cd .agents/skills/video-edit/remotion && npm install"))
    # every script / reference named in SKILL.md must exist (stale paths are a common skill failure)
    import re
    txt = (SKILL / "SKILL.md").read_text()
    missing = [m for m in set(re.findall(r"\$S/([\w\-]+\.py)", txt)) if not (SKILL / "scripts" / m).exists()]
    missing += [m for m in set(re.findall(r"references/([\w\-]+\.md)", txt)) if not (SKILL / "references" / m).exists()]
    req.append(item("SKILL.md paths exist", not missing, "fix stale paths in SKILL.md: " + ", ".join(missing)))
    ok = all(i["ok"] for i in req)
    print(json.dumps(dict(ok=ok, required=req, optional=opt), indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
