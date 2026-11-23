#!/usr/bin/env python
"""Fine-grained look at one clip: a labelled, tone-mapped sheet at chosen times (coarse -> fine passes).

  peek.py <folder> <file> --times 12.5,13,13.5          explicit timestamps
  peek.py <folder> <file> --span 20 30 --step 0.5       a range at a fixed step (use for a cut-point decision)
  peek.py <folder> <file> --times 40 --centroid         also print the brightness-weighted centre (x,y in 0..1) per frame,
                                                        handy as the zoom centre for a lit subject on a dark scene
Writes <folder>/_work/peek/<stem>_<hash>.jpg and prints its path + JSON. Look at the image, then decide.
Decodes with a fast seek per frame (-ss before -i); for B-frame-heavy footage prefer --span over many --times.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from vlib import probe, make_luts, md5
from analyze import contact_sheet, read_raw, color_chain, proxy_size


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder"); ap.add_argument("file")
    ap.add_argument("--times", default=""); ap.add_argument("--span", nargs=2, type=float); ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--long-edge", type=int, default=480); ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--centroid", action="store_true")
    a = ap.parse_args()
    folder = Path(a.folder).resolve(); path = folder / a.file
    info = probe(path)
    if info is None:
        sys.exit("not a video: use the photo directly")
    times = [float(x) for x in a.times.split(",") if x] if a.times else []
    if a.span:
        times += list(np.arange(a.span[0], a.span[1] + 1e-6, a.step))
    if not times:
        sys.exit("give --times or --span")
    times = sorted(set(round(t, 3) for t in times))[:48]
    W, H = proxy_size(info, a.long_edge)
    luts = make_luts(folder / "_work" / "luts")
    chain = color_chain(info, luts["pq2sdr"]).format(W=W, H=H)
    frames, labels, cent = [], [], []
    for t in times:
        res, _ = read_raw(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", chain,
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], (W, H), 3)
        if res is None or len(res[0]) == 0:
            continue
        fr = res[0][0]; frames.append(fr); labels.append(f"{t:.2f}s")
        if a.centroid:
            g = fr.mean(2)[: int(H * 0.72)].astype(np.float32) ** 2          # ignore the bottom 28% (UI / ground)
            ys, xs = np.mgrid[0:g.shape[0], 0:g.shape[1]]
            tot = g.sum() + 1e-9
            cent.append(dict(t=t, x=round(float((g * xs).sum() / tot / W), 3), y=round(float((g * ys).sum() / tot / H), 3)))
    if not frames:
        sys.exit("no frames decoded (time beyond the clip?)")
    out = folder / "_work" / "peek" / f"{path.stem}_{md5(times)}.jpg"
    contact_sheet(frames, None, labels, out, cell_h=int(H * 0.8) if H > 400 else H, cols=a.cols, gamma=1.15 if info["hdr"] else 1.0)
    print(json.dumps(dict(sheet=str(out), frames=len(frames), centroids=cent or None, clip_duration=info["duration"])))


if __name__ == "__main__":
    main()
