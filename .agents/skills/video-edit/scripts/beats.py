#!/usr/bin/env python
"""Beat grid for beat-synced cuts (librosa). The track is used for TIMING only; reels stay silent.

  .venv/bin/python scripts/beats.py track.mp3                    # tempo + beat times
  .venv/bin/python scripts/beats.py track.mp3 --every 2          # cut grid on every 2nd beat
  .venv/bin/python scripts/beats.py track.mp3 --every 2 --shots 12 [--start 0]   # 12 suggested shot lengths

Also imported by sample_reel.py (`--beats track.mp3 --every 2`) to snap SHOTS durations to the grid.
"""
import argparse, json
import numpy as np


def beat_grid(path, every=2, start=0.0, min_gap=0.35):
    """Return (tempo_bpm, beat_times, cut_times). cut_times = every Nth beat, >= min_gap apart."""
    import librosa
    y, sr = librosa.load(path, sr=22050, mono=True)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beats = librosa.frames_to_time(frames, sr=sr)
    beats = beats[beats >= start]
    cuts = []
    for t in beats[::max(1, every)]:
        if not cuts or t - cuts[-1] >= min_gap:
            cuts.append(float(t))
    return float(np.atleast_1d(tempo)[0]), [float(b) for b in beats], cuts


def snap_durations(durs, cuts, start=0.0):
    """Snap each shot length so every cut lands on the nearest later-or-equal grid point."""
    out, t = [], start
    grid = np.array([start] + list(cuts))
    for d in durs:
        target = t + d
        nxt = grid[np.argmin(np.abs(grid - target))]
        if nxt <= t + 0.2:                       # never collapse a shot
            later = grid[grid > t + 0.2]
            nxt = later[0] if len(later) else target
        out.append(round(float(nxt - t), 3)); t = nxt
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("track"); ap.add_argument("--every", type=int, default=2)
    ap.add_argument("--start", type=float, default=0.0); ap.add_argument("--shots", type=int)
    a = ap.parse_args()
    tempo, beats, cuts = beat_grid(a.track, a.every, a.start)
    res = {"tempo_bpm": round(tempo, 1), "beats": len(beats), "cut_times": [round(c, 3) for c in cuts]}
    if a.shots:
        res["shot_lengths"] = [round(b - a_, 3) for a_, b in zip([a.start] + cuts, cuts)][:a.shots]
    print(json.dumps(res, indent=1))
