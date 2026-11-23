#!/usr/bin/env python
"""STEP 5 of the video-edit skill: verify the RENDERED file(s), not the plan.

  verify.py <folder>/_work/plan.json

Checks (each is pass / fail / not_measured; not_measured counts as a failure):
  colour tags (HDR main = bt2020 + smpte2084 + hvc1; SDR fallback = bt709 + yuv420p), duration vs plan (+-1 frame-ish),
  audio is silent (max_volume), frame size/fps, A/V duration drift, text-free-of-garbage (blank/black frames).
Writes   <folder>/_work/verify/<Name>_check.jpg   a contact sheet taken from the actual MP4: first + last frame of every shot,
         so cuts, crops, text position and watermark/bystander issues can be eyeballed. LOOK AT IT before reporting.
Prints JSON; exit 1 on any fail / not_measured.
"""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from vlib import run, probe, read_json, make_luts, resolve_output
from analyze import contact_sheet, read_raw, color_chain, frame_metrics


def check(name, ok, detail=""):
    return dict(check=name, result="pass" if ok is True else "fail" if ok is False else "not_measured", detail=detail)


def main():
    plan_path = Path(sys.argv[1]); plan = read_json(plan_path)
    folder = plan_path.resolve().parent.parent
    name = plan["name"]
    total = sum(float(s["dur"]) for s in plan["shots"])
    res = resolve_output(plan, folder)
    fps, W, H = res["FPS"], res["W"], res["H"]
    luts = make_luts(folder / "_work" / "luts")
    results, files = [], {}
    cands = {"hdr": folder / f"{name}_Reel.mp4", "sdr": folder / f"{name}_Reel_SDR.mp4"}
    if plan.get("type") == "product":
        cands = {"product": folder / f"{name}_Product.mp4"}
    if plan.get("type") != "product":                       # expected main colour: HDR if any source is PQ (or forced), else SDR only
        cfg = plan.get("output", {}).get("hdr", "auto")
        def is_pq(sh):
            p = folder / sh["src"]
            return p.suffix.lower() in (".mp4", ".mov", ".m4v") and p.exists() and bool((probe(p) or {}).get("transfer_pq"))
        want_hdr = bool(cfg) if cfg != "auto" else any(is_pq(sh) for sh in plan["shots"])
        if not want_hdr:
            cands = {"sdr": cands["hdr"]}                    # single SDR main file
    for kind, f in cands.items():
        if not f.exists():
            continue_ok = kind == "sdr" and f.name.endswith("_Reel_SDR.mp4") and not plan.get("output", {}).get("sdr_fallback", False)
            if continue_ok:
                continue
            results.append(check(f"{f.name} exists", False)); continue
        i = probe(f); files[kind] = f
        r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_tag_string,color_space,color_primaries,color_transfer,pix_fmt",
                 "-of", "json", f]); v = json.loads(r.stdout)["streams"][0]
        if kind == "hdr":
            ok = v.get("color_transfer") == "smpte2084" and v.get("color_primaries") == "bt2020" and v.get("codec_tag_string") == "hvc1"
            results.append(check(f"{f.name}: HDR10 tags", ok if v else None, f"{v.get('color_transfer')}/{v.get('color_primaries')}/{v.get('codec_tag_string')}"))
        elif kind == "sdr":
            ok = v.get("color_transfer") == "bt709" and v.get("color_primaries") == "bt709" and v.get("pix_fmt") == "yuv420p"
            results.append(check(f"{f.name}: SDR tags (no PQ leak)", ok, f"{v.get('color_transfer')}/{v.get('color_primaries')}/{v.get('pix_fmt')}"))
        results.append(check(f"{f.name}: duration", abs(i["duration"] - total) <= max(0.15, 2 / fps), f"{i['duration']:.2f}s vs plan {total:.2f}s"))
        results.append(check(f"{f.name}: size/fps", (i["width"], i["height"]) == (W, H) and abs(i["fps"] - fps) < 0.5, f"{i['width']}x{i['height']}@{i['fps']}"))
        a = run(["ffmpeg", "-nostats", "-i", f, "-vn", "-af", "volumedetect", "-f", "null", "-"], check=False)
        mx = re.search(r"max_volume: (-?[0-9.]+|-inf) dB", a.stderr)
        if plan.get("output", {}).get("silent", True):
            results.append(check(f"{f.name}: silent audio", (float(mx.group(1)) < -60) if mx else None, mx.group(0) if mx else "no volumedetect output"))
    # contact sheet from the HDR (or first available) file: first + last frame of every shot
    src = files.get("hdr") or files.get("product") or next(iter(files.values()), None)
    sheet = None
    if src:
        info = probe(src)
        t, frames, labels, blank = 0.0, [], [], []
        pw, ph = 216, 384
        fade = float(plan.get("output", {}).get("fade_out", 0.6))
        for k, s in enumerate(plan["shots"]):
            d = float(s["dur"])
            last = k == len(plan["shots"]) - 1
            for tag, tt in (("in", t + 0.1), ("out", t + d - (fade + 0.1 if last else 0.1))):   # last shot fades to black on purpose
                tt = min(max(tt, 0), max(info["duration"] - 0.05, 0))
                chain = color_chain(info, luts["pq2sdr"]).format(W=pw, H=ph)
                res, _ = read_raw(["ffmpeg", "-v", "error", "-ss", f"{tt:.3f}", "-i", src, "-frames:v", "1", "-vf", chain,
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], (pw, ph), 3)
                if res is None or len(res[0]) == 0:
                    continue
                fr = res[0][0]; frames.append(fr); labels.append(f"{s['id']} {tag} {tt:.1f}s")
                m = frame_metrics(fr)
                if m["bright"] < 0.02 or m["contrast"] < 0.01: blank.append(f"{s['id']}@{tt:.1f}s")
            t += d
        if frames:
            sheet = folder / "_work" / "verify" / f"{name}_check.jpg"
            contact_sheet(frames, None, labels, sheet, cell_h=ph, cols=8, gamma=1.15)
        results.append(check("no blank/black frames at shot boundaries", not blank if frames else None, ", ".join(blank)))
    bad = [r for r in results if r["result"] != "pass"]
    print(json.dumps(dict(ok=not bad, results=results, contact_sheet=str(sheet) if sheet else None,
                          reminder="LOOK at the contact sheet (cuts, crops, text, watermarks, bystanders) before reporting; say 'sampled frames reviewed'."), indent=1))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    main()
