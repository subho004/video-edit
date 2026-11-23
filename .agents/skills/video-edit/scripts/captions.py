#!/usr/bin/env python
"""Word-level captions with whisper.cpp (local, nothing uploaded).

  .venv/bin/python scripts/captions.py talk.mp4                  # -> talk.captions.json (Remotion Caption format)
  .venv/bin/python scripts/captions.py talk.mp4 --model models/ggml-base.en.bin --out my.json

Output: [{"text": " word", "startMs": 0, "endMs": 420, "timestampMs": 210, "confidence": null}, ...]
which the Remotion template (remotion/) reads directly. Needs `brew install whisper-cpp` and a ggml model
(see README). Model path can also come from $WHISPER_MODEL.
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def transcribe(media, model, out=None):
    out = Path(out) if out else Path(media).with_suffix(".captions.json")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr)
        base = Path(td) / "w"
        r = subprocess.run(["whisper-cli", "-m", str(model), "-f", str(wav), "-ojf", "-of", str(base), "-ml", "1", "-sow", "-np"],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr[-2000:])
        data = json.loads((Path(str(base) + ".json")).read_text())
    words = []
    for seg in data.get("transcription", []):
        txt = seg["text"]
        if not txt.strip() or txt.strip().startswith("["):      # [BLANK_AUDIO] etc.
            continue
        s, e = seg["offsets"]["from"], seg["offsets"]["to"]
        words.append({"text": txt, "startMs": s, "endMs": e, "timestampMs": (s + e) // 2, "confidence": None})
    out.write_text(json.dumps(words, indent=1))
    return out, len(words)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("media"); ap.add_argument("--out")
    ap.add_argument("--model", default=os.environ.get("WHISPER_MODEL", str(ROOT / "models" / "ggml-base.en.bin")))
    a = ap.parse_args()
    if not Path(a.model).exists():
        sys.exit(f"model not found: {a.model}  (see README: download a ggml model)")
    o, n = transcribe(a.media, a.model, a.out)
    print(f"{n} words -> {o}")
