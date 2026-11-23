#!/usr/bin/env python
"""Shot / scene detection (PySceneDetect) to find clean cut points inside long or multi-shot clips.

  .venv/bin/python scripts/scenes.py clip.mp4                  # list scenes (start, end, seconds)
  .venv/bin/python scripts/scenes.py clip.mp4 --threshold 20   # more sensitive (default 27, content detector)
  .venv/bin/python scripts/scenes.py clip.mp4 --json

Clips with no hard cuts (one continuous take) come back as a single scene: pick cut points visually.
Detection runs on a downscaled copy of the frames, so 4K HEVC is fine.
"""
import argparse, json
from scenedetect import open_video, SceneManager, ContentDetector


def detect(path, threshold=27.0, min_len=0.5):
    video = open_video(path)
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=threshold, min_scene_len=int(min_len * video.frame_rate)))
    sm.auto_downscale = True
    sm.detect_scenes(video, show_progress=False)
    scenes = sm.get_scene_list() or [(video.base_timecode, video.duration)]
    return [(s.seconds, e.seconds) for s, e in scenes]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("clip"); ap.add_argument("--threshold", type=float, default=27.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sc = detect(a.clip, a.threshold)
    if a.json:
        print(json.dumps([{"start": round(s, 2), "end": round(e, 2)} for s, e in sc]))
    else:
        for i, (s, e) in enumerate(sc):
            print(f"{i:02d}  {s:8.2f} -> {e:8.2f}   ({e - s:.2f}s)")
