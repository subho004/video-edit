#!/usr/bin/env python
"""STEP 1 of the video-edit skill: analyse every clip / photo in a footage folder and write a JSON map.

  .venv/bin/python skills/video-edit/scripts/analyze.py <folder> [--jobs 2] [--win 3] [--force]

Writes   <folder>/_work/analysis/map.json          objective metrics, camera-motion segments, ranked candidate
                                                    windows, flags, duplicates, decisions_needed hints
         <folder>/_work/analysis/sheets/*.jpg      labelled contact sheets (one per clip) + overview.jpg
The agent then LOOKS at the sheets (tone-mapped, timestamped) and fills the "agent" block of each clip in map.json
(subject, shot_type, use, privacy notes). Numbers are cheap hints; the agent's eyes make the final call.
Nothing is modified outside <folder>/_work/. Re-runs are cached per clip (use --force to redo).
"""
import argparse, concurrent.futures as cf, datetime, json, re, sys, time
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from vlib import (run, probe, write_json, read_json, md5, make_luts, folder_media, REPO)

SCHEMA = "video-edit/analysis-map@1"
YUNET = REPO / "models" / "face_detection_yunet_2023mar.onnx"
PROXY = 640            # long edge of the analysis frames
MAX_SAMPLES = 200


# ------------------------------------------------------------------ frame extraction
def proxy_size(info, long_edge=PROXY):
    w, h = info["width"], info["height"]
    s = long_edge / max(w, h)
    return max(2, int(round(w * s / 2)) * 2), max(2, int(round(h * s / 2)) * 2)


def color_chain(info, lut):
    if info.get("hdr") and info.get("color_transfer") == "smpte2084":
        return f"scale={{W}}:{{H}}:in_color_matrix=bt2020:in_range=tv:out_range=full:flags=bilinear,format=gbrp16le,lut3d=file={lut},format=rgb24"
    return "scale={W}:{H}:flags=bilinear,format=rgb24"


def read_raw(cmd, size, channels, want_times=False):
    """Run ffmpeg -> rawvideo on stdout, return list of arrays (+ pts_times parsed from showinfo)."""
    import subprocess
    p = subprocess.run([str(c) for c in cmd], capture_output=True)
    if p.returncode and not p.stdout:
        return None, p.stderr.decode(errors="ignore")[-800:]
    w, h = size
    n = len(p.stdout) // (w * h * channels)
    arr = np.frombuffer(p.stdout[: n * w * h * channels], np.uint8).reshape(n, h, w, channels) if channels > 1 \
        else np.frombuffer(p.stdout[: n * w * h], np.uint8).reshape(n, h, w)
    times = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", p.stderr.decode(errors="ignore"))] if want_times else None
    return (arr, times), ""


def sample_frames(path, info, lut, dur):
    """Return (frames[n,h,w,3] RGB, times[n]). Regular fps sampling; keyframes-only for very long clips."""
    W, H = proxy_size(info)
    chain = color_chain(info, lut).format(W=W, H=H)
    base = ["ffmpeg", "-v", "info", "-nostats"]
    for hw in (["-hwaccel", "videotoolbox"], []):
        if dur > 360:      # long clip: decode keyframes only, timestamps from showinfo
            cmd = base + hw + ["-skip_frame", "nokey", "-i", path, "-an", "-vf", chain + ",showinfo",
                               "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
            res, err = read_raw(cmd, (W, H), 3, want_times=True)
            if res:
                arr, times = res
                times = times[: len(arr)]
                if len(arr) > MAX_SAMPLES:
                    idx = np.linspace(0, len(arr) - 1, MAX_SAMPLES).astype(int)
                    arr, times = arr[idx], [times[i] for i in idx]
                return arr, [round(t, 3) for t in times], "keyframes"
        else:
            step = 0.5 if dur < 10 else 1.0 if dur <= MAX_SAMPLES else dur / MAX_SAMPLES
            cmd = base + hw + ["-i", path, "-an", "-vf", f"fps=1/{step:.4f}:start_time=0," + chain,
                               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
            res, err = read_raw(cmd, (W, H), 3)
            if res:
                arr = res[0]
                return arr, [round(i * step, 3) for i in range(len(arr))], f"fps=1/{step:.2f}"
    sys.exit(f"could not decode {path}: {err}")


def motion_frames(path, dur, probe_windows, h):
    """Gray 5 fps proxy frames. Whole clip if short, otherwise short probe windows. -> list of (t0, frames)"""
    out = []
    for t0, t1 in probe_windows:
        cmd = ["ffmpeg", "-v", "error", "-hwaccel", "videotoolbox", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", path,
               "-an", "-vf", f"fps=5,scale=160:{h}:flags=bilinear,format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
        import subprocess
        p = subprocess.run([str(c) for c in cmd], capture_output=True)
        if p.returncode and not p.stdout:
            cmd = [c for c in cmd if c not in ("-hwaccel", "videotoolbox")]
            p = subprocess.run([str(c) for c in cmd], capture_output=True)
        if not p.stdout:
            continue
        out.append((t0, p.stdout))
    return out


# ------------------------------------------------------------------ metrics
_yunet = {}
_yunet_lock = __import__("threading").Lock()


def faces_in(rgb):
    """YuNet: -> (count, largest_face_height_fraction, any_near_edge). Low-res, so only a high-precision hint."""
    if not YUNET.exists():
        return None
    h, w = rgb.shape[:2]
    key = (w, h)
    with _yunet_lock:                      # the DNN graph is not thread-safe and is bound to one input size
        if key not in _yunet:
            _yunet[key] = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.7, 0.3, 200)
        _, f = _yunet[key].detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    if f is None:
        return 0, 0.0, False
    hf = float(max(r[3] for r in f)) / h
    edge = any(r[0] < 0.04 * w or r[0] + r[2] > 0.96 * w for r in f)
    return len(f), round(hf, 3), bool(edge)


def frame_metrics(rgb):
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    lap = cv2.Laplacian(g, cv2.CV_64F).var()
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    gf = g.astype(np.float32) / 255
    return dict(sharp=float(lap), bright=float(gf.mean()), contrast=float(gf.std()),
                dark=float((gf < 0.04).mean()), clip=float((gf > 0.98).mean()), sat=float(hsv[..., 1].mean() / 255))


def dhash(rgb, n=8):
    g = cv2.resize(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (n + 1, n), interpolation=cv2.INTER_AREA)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def ham(a, b):
    return bin(a ^ b).count("1")


def merge_runs(rows):
    segs = []
    for r in rows:
        if segs and segs[-1]["camera"] == r["cls"] and abs(segs[-1]["end"] - r["t"]) < 1.01:
            segs[-1]["end"] = round(r["t"] + 1, 2)
        else:
            segs.append(dict(start=r["t"], end=round(r["t"] + 1, 2), camera=r["cls"]))
    return segs


# ------------------------------------------------------------------ candidates
def make_candidates(times, S, motion_rows, dur, win, cut_times):
    """Slide a window over the clip; score = sharpness*exposure*steadiness*interest minus privacy/cut penalties."""
    if dur <= 0 or len(times) == 0:
        return []
    t = np.array(times)
    sharp = np.array([s["sharp"] for s in S]); med = np.median(sharp) + 1e-9
    sharp_n = np.clip(sharp / (1.3 * med), 0, 1)
    expo = np.array([1.0 - min(1.0, 2.5 * s["clip"] + 2.0 * s["dark"] + (0.5 if s["bright"] < 0.08 else 0)) for s in S])
    face = np.array([s.get("face_h", 0) for s in S])
    nfaces = np.array([s.get("faces", 0) for s in S])
    mt = np.array([r["t"] for r in motion_rows]) if motion_rows else np.array([])

    def motion_at(a, b):
        if not len(mt):
            return None
        sel = [r for r in motion_rows if a <= r["t"] < b]
        return sel or None

    cands, W = [], min(win, dur)
    starts = np.arange(0, max(dur - W, 0) + 1e-6, 0.5)
    for a in starts:
        b = a + W
        idx = np.where((t >= a - 0.01) & (t < b))[0]
        if len(idx) == 0:
            continue
        sc, why, flags = 0.0, [], []
        sc += 0.30 * float(sharp_n[idx].mean())
        sc += 0.20 * float(expo[idx].mean())
        mr = motion_at(a, b)
        if mr:
            shaky = np.mean([r["cls"] == "handheld_shaky" for r in mr])
            cutf = any(r["cls"] == "cut" for r in mr)
            energy = float(np.mean([r["energy"] for r in mr]))
            steady = 1.0 - min(1.0, 3 * shaky)
            interest = min(1.0, energy / 0.04) * 0.6 + 0.4 * (1 - shaky)
            sc += 0.25 * steady + 0.15 * interest
            if shaky > 0.4: flags.append("shaky")
            if cutf: sc -= 0.5; flags.append("contains_cut")
            kinds = [r["cls"] for r in mr]
            why.append("camera:" + max(set(kinds), key=kinds.count))
        else:
            sc += 0.25 * 0.7 + 0.15 * 0.5                     # unknown motion -> neutral
        if any(a < c < b for c in cut_times):
            sc -= 0.5; flags.append("contains_cut") if "contains_cut" not in flags else None
        if face[idx].max() >= 0.06:
            sc -= 0.30; flags.append("face_in_frame")
        elif nfaces[idx].max() > 0:
            sc -= 0.10; flags.append("small_face_possible")
        if sharp_n[idx].mean() > 0.85: why.append("sharp")
        if expo[idx].mean() < 0.7: flags.append("exposure_issue")
        cands.append(dict(start=round(float(a), 2), end=round(float(b), 2), score=round(float(sc), 3),
                          why=why, flags=sorted(set(flags))))
    cands.sort(key=lambda c: -c["score"])
    pick = []
    for c in cands:                                           # non-overlapping top windows
        if all(c["end"] <= p["start"] or c["start"] >= p["end"] for p in pick):
            pick.append(c)
        if len(pick) >= 6:
            break
    return pick


# ------------------------------------------------------------------ contact sheets
def font(sz):
    for p in ("/System/Library/Fonts/Avenir Next.ttc", "/System/Library/Fonts/Helvetica.ttc",
              "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def contact_sheet(frames, times, labels, out, cell_h=320, cols=6, gamma=1.0):
    h, w = frames[0].shape[:2]
    cw, ch = int(round(w * cell_h / h)), cell_h
    rows = int(np.ceil(len(frames) / cols))
    im = Image.new("RGB", (cols * cw, rows * ch), (20, 20, 20))
    d = ImageDraw.Draw(im); f = font(max(12, ch // 16))
    lut = (np.linspace(0, 1, 256) ** (1 / gamma) * 255).astype(np.uint8) if gamma != 1.0 else None
    for i, (fr, lab) in enumerate(zip(frames, labels)):
        x, y = (i % cols) * cw, (i // cols) * ch
        pil = Image.fromarray(lut[fr] if lut is not None else fr).resize((cw, ch), Image.BILINEAR)
        im.paste(pil, (x, y))
        d.rectangle([x, y, x + cw, y + ch // 9], fill=(0, 0, 0))
        d.text((x + 4, y + 1), lab, fill=(255, 255, 0), font=f)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=82)


# ------------------------------------------------------------------ per-clip analysis
def analyze_video(path, cid, luts, A, win, args):
    info = probe(path)
    dur = info["duration"]
    frames, times, how = sample_frames(path, info, luts["pq2sdr"], dur)
    if len(frames) == 0:
        return dict(kind="video", probe=info, flags=["undecodable_or_empty"], candidates=[], hashes=["0000000000000000"],
                    sampling=dict(method=how, samples=0), metrics={}, sheet=None)
    S = []
    for fr in frames:
        m = frame_metrics(fr)
        f = faces_in(fr)
        if f is not None:
            m["faces"], m["face_h"], m["face_edge"] = f
        S.append(m)
    # motion pass
    if dur <= 240:
        windows = [(0.0, dur)]
    else:
        n = 24
        windows = [(float(s), float(min(s + 4, dur))) for s in np.linspace(0, max(dur - 4, 0), n)]
    mh = max(2, int(round(160 * info["height"] / info["width"] / 2)) * 2)
    rows = []
    for t0, buf in motion_frames(path, dur, windows, mh):
        rows += motion_rows(t0, buf, mh)
    cuts = [r["t"] for r in rows if r["cls"] == "cut"]
    scenes = None
    if dur <= 300:
        try:
            from scenedetect import open_video, SceneManager, ContentDetector
            v = open_video(str(path)); sm = SceneManager(); sm.auto_downscale = True
            sm.add_detector(ContentDetector(threshold=27.0, min_scene_len=int(0.5 * (v.frame_rate or 30))))
            sm.detect_scenes(v, show_progress=False)
            scenes = [[round(s.seconds, 2), round(e.seconds, 2)] for s, e in sm.get_scene_list()]
            cuts = sorted(set(cuts + [b for _, b in scenes[:-1]]))
        except Exception as e:                                # scenedetect optional
            scenes = None
    cands = make_candidates(times, S, rows, dur, win, cuts)
    # audio
    audio = None
    if info["has_audio"]:
        r = run(["ffmpeg", "-nostats", "-i", path, "-vn", "-af", "volumedetect", "-f", "null", "-"], check=False)
        mm = re.search(r"mean_volume: (-?[0-9.]+) dB", r.stderr); mx = re.search(r"max_volume: (-?[0-9.]+) dB", r.stderr)
        if mm:
            audio = dict(mean_db=float(mm.group(1)), max_db=float(mx.group(1)) if mx else None)
            audio["level"] = "silent" if audio["mean_db"] < -60 else "quiet" if audio["mean_db"] < -35 else "normal" if audio["mean_db"] < -22 else "loud"
    hashes = [f"{dhash(frames[int(q * (len(frames) - 1))]):016x}" for q in (0.25, 0.5, 0.75)]
    sharp = np.array([s["sharp"] for s in S])
    summary = dict(
        sharp_median=round(float(np.median(sharp)), 1), sharp_p10=round(float(np.percentile(sharp, 10)), 1),
        brightness_mean=round(float(np.mean([s["bright"] for s in S])), 3),
        clip_frac=round(float(np.mean([s["clip"] for s in S])), 4), dark_frac=round(float(np.mean([s["dark"] for s in S])), 4),
        motion_energy_mean=round(float(np.mean([r["energy"] for r in rows])), 4) if rows else None,
        faces_max=int(max([s.get("faces", 0) for s in S])), face_h_max=max([s.get("face_h", 0) for s in S]))
    flags = []
    if info["hdr"]: flags.append("hdr")
    if info["vfr"]: flags.append("vfr")
    if min(info["width"], info["height"]) < 1000: flags.append("low_res")
    if summary["brightness_mean"] < 0.15: flags.append("dark")
    if summary["clip_frac"] > 0.05: flags.append("blown_highlights")
    if summary["faces_max"] > 0: flags.append("faces_possible")
    if rows and np.mean([r["cls"] == "handheld_shaky" for r in rows]) > 0.4: flags.append("shaky")
    if dur > 300: flags.append("long_clip_pick_sections")
    if dur < 1.5: flags.append("very_short")
    if info["orientation"] != "portrait": flags.append(f"{info['orientation']}_needs_reframe")
    if re.search(r"-WA\d+", Path(path).stem): flags.append("messenger_export_soft_or_watermarked")
    # sheet
    n_cells = 24 if dur < 120 else 36
    idx = np.linspace(0, len(frames) - 1, min(n_cells, len(frames))).astype(int)
    sheet = A / "sheets" / f"{cid}.jpg"
    contact_sheet([frames[i] for i in idx], [times[i] for i in idx],
                  [f"{times[i]:.1f}s" + (" F" if S[i].get("faces") else "") for i in idx],
                  sheet, cols=6 if info["orientation"] == "portrait" else 4, cell_h=320 if info["orientation"] == "portrait" else 200,
                  gamma=1.15 if info["hdr"] else 1.0)
    best = cands[0] if cands else None
    mid = frames[len(frames) // 2] if not best else frames[int(np.argmin(np.abs(np.array(times) - (best["start"] + best["end"]) / 2)))]
    thumb_path = A / "thumbs" / f"{cid}.npy"; thumb_path.parent.mkdir(exist_ok=True, parents=True)
    np.save(thumb_path, mid)
    return dict(kind="video", probe=info, sampling=dict(method=how, samples=len(times)),
                metrics=summary, timeline=dict(t=times, sharp=[round(s["sharp"], 1) for s in S],
                                                bright=[round(s["bright"], 3) for s in S],
                                                faces=[s.get("faces", 0) for s in S]),
                camera_segments=merge_runs(rows) if rows else [], motion_seconds=[[r["t"], r["cls"], r["energy"]] for r in rows][:1000],
                scenes=scenes, cut_times=[round(c, 2) for c in cuts], candidates=cands, audio=audio, hashes=hashes,
                flags=flags, sheet=str(sheet.relative_to(A)))


def motion_rows(t0, buf, h, w=160):
    n = len(buf) // (w * h)
    if n < 3:
        return []
    fr = np.frombuffer(buf[: n * w * h], np.uint8).reshape(n, h, w)
    # reuse motion_analysis logic by re-packing (it infers h from size); simpler: inline call with known h
    rows = []
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    ff = fr.astype(np.float32)
    d = []
    for i in range(1, n):
        diff = float(np.abs(ff[i] - ff[i - 1]).mean() / 255)
        (dx, dy), resp = cv2.phaseCorrelate(ff[i - 1], ff[i], win)
        d.append((t0 + i / 5, diff, dx / w, dy / h))
    for s in range(0, len(d) - 4, 5):
        blk = d[s:s + 5]
        en = float(np.mean([b[1] for b in blk]))
        dx = np.array([b[2] for b in blk]); dy = np.array([b[3] for b in blk])
        cut = max(b[1] for b in blk) > 0.22
        mdx, mdy = float(dx.mean()), float(dy.mean())
        jit = float(np.std(np.diff(dy)) + np.std(np.diff(dx))) / 2
        if cut: cls = "cut"
        elif en < 0.006 and abs(mdx) < 0.004 and abs(mdy) < 0.004: cls = "static"
        elif abs(mdx) > 0.012 and abs(mdx) > 2.5 * abs(mdy) and np.sign(dx).std() < 0.9: cls = "pan_right" if mdx < 0 else "pan_left"
        elif abs(mdy) > 0.012 and abs(mdy) > 2.5 * abs(mdx) and np.sign(dy).std() < 0.9: cls = "tilt_up" if mdy > 0 else "tilt_down"
        elif jit > 0.01: cls = "handheld_shaky"
        elif en > 0.03: cls = "moving"
        else: cls = "gentle"
        rows.append(dict(t=round(blk[0][0] - 0.2, 2), energy=round(en, 4), dx=round(mdx, 4), dy=round(mdy, 4),
                         jitter=round(jit, 4), cls=cls))
    return rows


def analyze_image(path, cid, A, args):
    conv = A / "conv"; conv.mkdir(parents=True, exist_ok=True)
    src = Path(path); use = src
    if src.suffix.lower() in (".heic", ".heif"):
        use = conv / (src.stem + ".png")
        if not use.exists():
            run(["sips", "-s", "format", "png", src, "--out", use])
    info = probe(use)
    W, H = proxy_size(info)
    r, _ = read_raw(["ffmpeg", "-v", "error", "-i", use, "-vf", f"scale={W}:{H}:flags=bilinear,format=rgb24",
                     "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], (W, H), 3)
    fr = r[0][0]
    m = frame_metrics(fr); f = faces_in(fr)
    if f is not None:
        m["faces"], m["face_h"], m["face_edge"] = f
    flags = []
    if src.suffix.lower() in (".heic", ".heif"): flags.append("display_p3_source")
    if min(info["width"], info["height"]) < 1000: flags.append("low_res")
    if re.search(r"-WA\d+", src.stem): flags.append("messenger_export_soft_or_watermarked")
    if m.get("faces"): flags.append("faces_possible")
    if m["bright"] < 0.15: flags.append("dark")
    if info["orientation"] != "portrait": flags.append(f"{info['orientation']}_needs_reframe")
    (A / "thumbs").mkdir(parents=True, exist_ok=True)
    np.save(A / "thumbs" / f"{cid}.npy", fr)
    return dict(kind="image", probe=dict(width=info["width"], height=info["height"], orientation=info["orientation"],
                                          size_mb=info["size_mb"], source_ext=src.suffix.lower(), converted=str(use.relative_to(A.parent)) if use != src else None),
                metrics={k: round(v, 3) if isinstance(v, float) else v for k, v in m.items()},
                hashes=[f"{dhash(fr):016x}"], flags=flags, candidates=[dict(start=0, end=0, score=round(float(min(1, m["sharp"] / 400) * 0.6 + 0.4), 3), why=["still"], flags=[])],
                sheet=None, _frame=fr)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder"); ap.add_argument("--jobs", type=int, default=2); ap.add_argument("--win", type=float, default=3.0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    folder = Path(args.folder).resolve()
    if not folder.is_dir():
        sys.exit(f"not a folder: {folder}")
    A = folder / "_work" / "analysis"; (A / "cache").mkdir(parents=True, exist_ok=True)
    luts = make_luts(folder / "_work" / "luts")
    vids, imgs = folder_media(folder)
    items = [("video", p) for p in vids] + [("image", p) for p in imgs]
    if not items:
        sys.exit(f"no media found in {folder}")
    ids = {p: f"c{i + 1:02d}" for i, (_, p) in enumerate(items)}
    t0 = time.time()

    def work(kp):
        kind, p = kp
        cid = ids[p]
        key = md5(str(p), p.stat().st_size, int(p.stat().st_mtime), args.win, "v1")
        cf_ = A / "cache" / f"{cid}_{key}.json"
        if cf_.exists() and not args.force and (A / "sheets" / f"{cid}.jpg").exists() | (kind == "image"):
            d = read_json(cf_)
        else:
            d = analyze_video(p, cid, luts, A, args.win, args) if kind == "video" else analyze_image(p, cid, A, args)
            d.pop("_frame", None)
            write_json(cf_, d)
        d.update(id=cid, file=p.name)
        print(f"  {cid} {p.name}  {d.get('probe', {}).get('duration', '')}  flags={d['flags']}", flush=True)
        return d

    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        clips = list(ex.map(work, items))
    # ordering fields
    for c in clips:
        c["agent"] = dict(subject=None, shot_type=None, use="unset", hero=False, privacy=None, notes=None)
    # preserve agent annotations from a previous map
    mp = A / "map.json"
    if mp.exists():
        try:
            old = {c["file"]: c for c in read_json(mp)["clips"]}
            for c in clips:
                if c["file"] in old and old[c["file"]].get("agent"):
                    c["agent"] = old[c["file"]]["agent"]
        except Exception:
            pass
    # softness relative to the rest of the folder (hint only: sharpness depends on content)
    meds = [c["metrics"]["sharp_median"] for c in clips if c["kind"] == "video" and c.get("metrics")]
    if len(meds) >= 3:
        fm = float(np.median(meds))
        for c in clips:
            if c["kind"] == "video" and c.get("metrics") and c["metrics"]["sharp_median"] < 0.4 * fm:
                c["flags"].append("soft_or_blurry_vs_folder")
                for cd in c["candidates"]:
                    cd["score"] = round(cd["score"] - 0.25, 3); cd["flags"].append("soft")
    # duplicates
    dup = []
    for i in range(len(clips)):
        for j in range(i + 1, len(clips)):
            ha, hb = clips[i]["hashes"], clips[j]["hashes"]
            dmin = min(ham(int(a, 16), int(b, 16)) for a in ha for b in hb)
            if dmin <= 8:
                dup.append(dict(a=clips[i]["id"], b=clips[j]["id"], distance=dmin))
    # overview sheet
    thumbs, labels = [], []
    for c in clips:
        tp = A / "thumbs" / f"{c['id']}.npy"
        if tp.exists():
            fr = np.load(tp)
            thumbs.append(fr)
            pr = c["probe"]
            labels.append(f"{c['id']} " + (f"{pr['duration']:.0f}s" if c["kind"] == "video" else "photo"))
    if thumbs:
        cell_w, cell_h = 216, 384                       # uniform portrait cell, letterboxed
        canvas = []
        for t in thumbs:
            k = min(cell_w / t.shape[1], cell_h / t.shape[0])
            r = cv2.resize(t, (max(1, int(t.shape[1] * k)), max(1, int(t.shape[0] * k))))
            c = np.zeros((cell_h, cell_w, 3), np.uint8)
            y0, x0 = (cell_h - r.shape[0]) // 2, (cell_w - r.shape[1]) // 2
            c[y0:y0 + r.shape[0], x0:x0 + r.shape[1]] = r
            canvas.append(c)
        contact_sheet(canvas, None, labels, A / "sheets" / "overview.jpg", cell_h=cell_h, cols=8, gamma=1.15)
    # decisions hints
    hints = []
    vclips = [c for c in clips if c["kind"] == "video"]
    if any(c["id"] and "faces_possible" in c["flags"] for c in clips):
        hints.append("Faces detected in some clips: confirm bystanders vs the subject, and whether to avoid or keep them.")
    if any("hdr" in c["flags"] for c in clips) and any("hdr" not in c["flags"] for c in clips):
        hints.append("Mixed HDR and SDR sources: default is an HDR main file with SDR sources mapped in (plus an SDR fallback).")
    if dup:
        hints.append("Near-duplicate clips found: choose which to keep.")
    if any("long_clip_pick_sections" in c["flags"] for c in clips):
        hints.append("Very long clip(s): ask which sections or moments matter.")
    if any(f.endswith("_needs_reframe") for c in clips for f in c["flags"]):
        hints.append("Landscape/square sources: confirm the 9:16 crop centre per clip.")
    if any("messenger_export_soft_or_watermarked" in c["flags"] for c in clips):
        hints.append("Messenger exports are soft and may carry a corner watermark: use them briefly and crop the corner.")
    hints += ["Always confirm: goal and platform, target length, text line (or none), music (timing only), and the hero shot / ending."]
    tot = sum(c["probe"]["duration"] for c in vclips)
    out = dict(schema=SCHEMA, created=datetime.datetime.now().isoformat(timespec="seconds"), folder=folder.name,
               summary=dict(videos=len(vclips), photos=len(clips) - len(vclips), total_video_seconds=round(tot, 1),
                            hdr_clips=sum("hdr" in c["flags"] for c in clips),
                            elapsed_s=round(time.time() - t0, 1)),
               clips=clips, duplicates=dup, decisions_needed=hints,
               how_to_read=dict(sheets="_work/analysis/sheets/<id>.jpg (timestamped; 'F' = face detected)", overview="_work/analysis/sheets/overview.jpg",
                                agent_block="After viewing the sheets, fill clips[*].agent: subject, shot_type, use (hook/body/ending/skip), hero, privacy, notes."))
    write_json(mp, out)
    print(f"\nmap: {mp}\noverview: {A / 'sheets' / 'overview.jpg'}\n{json.dumps(out['summary'])}")


if __name__ == "__main__":
    main()
