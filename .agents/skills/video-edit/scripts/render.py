#!/usr/bin/env python
"""STEP 4 of the video-edit skill: render a plan.json into the finished file(s).

  .venv/bin/python .agents/skills/video-edit/scripts/render.py <folder>/_work/plan.json [--only s3,s4] [--no-sdr] [--preview]

Default output is 4K (2160x3840) at the highest source frame rate (max 60), at high bitrate: the best quality the sources allow.
--preview renders a 1080x1920 draft (separate cache, <Name>_Reel_preview.mp4, HDR only) for quick review before the 4K render.

type "reel"    ffmpeg pipeline (silent, original look). Per-shot segments are cached as 10-bit ProRes in <folder>/_work/segments,
               then concatenated and encoded ONCE: HEVC HDR10 main file + H.264 SDR fallback.
               SDR sources (photos, WhatsApp-style clips) are mapped into the HDR file with 3D LUTs (never the other way round).
type "product" renders remotion/ (ProductReel template) with props from plan.product; see references/product-playbook.md.
Prints one JSON line: {"outputs": [...], "duration": s, "shots": n}. Run plan.py validate first.
"""
import argparse, json, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from vlib import run, probe, md5, make_luts, read_json, write_json, resolve_output, SKILL, REPO

PQ_WHITE = 0.5807      # PQ signal of a 203-nit diffuse white


def even(x):
    return max(2, int(round(x / 2)) * 2)


def crop_box(iw, ih, W, H, c):
    """Largest 9:16-style window of height hf*ih at fractional position (x, y) inside the source."""
    hf = float(c.get("hf", 1.0))
    ch = ih * hf; cw = ch * W / H
    if cw > iw:
        cw = iw; ch = cw * H / W
    cw, ch = even(cw), even(ch)
    x = int((iw - cw) * float(c.get("x", 0.5))); y = int((ih - ch) * float(c.get("y", 0.5)))
    return cw, ch, x - x % 2, y - y % 2


def source_kind(path):
    """-> (kind, color) kind: video|image ; color: pq (HDR), sdr709, p3"""
    ext = path.suffix.lower()
    if ext in (".heic", ".heif"):
        return "image", "p3"
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"):
        return "image", "sdr709"
    info = probe(path)
    return "video", "pq" if info["transfer_pq"] else "sdr709"


def to_pq_chain(color, luts):
    """filters that take an RGB/YUV SDR frame to PQ BT.2020 yuv422p10le"""
    lut = luts["sdrP3_to_pq"] if color == "p3" else luts["sdr709_to_pq"]
    return f"format=gbrp16le,lut3d=file={lut},scale=out_color_matrix=bt2020nc:out_range=tv,format=yuv422p10le"


def render_segment(i, shot, ctx):
    W, H, FPS, SRC, WORK, luts = ctx["W"], ctx["H"], ctx["FPS"], ctx["SRC"], ctx["WORK"], ctx["luts"]
    path = SRC / shot["src"]
    if not path.exists():
        sys.exit(f"{shot['id']}: source not found: {path}")
    kind, color = source_kind(path)
    if path.suffix.lower() in (".heic", ".heif"):                 # sips -> png (EXIF orientation is baked in by ffmpeg autorotate)
        conv = WORK / "conv" / (path.stem + ".png"); conv.parent.mkdir(parents=True, exist_ok=True)
        if not conv.exists():
            run(["sips", "-s", "format", "png", path, "--out", conv])
        path = conv
    st = path.stat()
    key = md5(shot, ctx["version"], st.st_size, int(st.st_mtime), W, H, FPS)
    seg = WORK / "segments" / f"{i:02d}_{shot['id']}_{key}.mov"
    if seg.exists():
        return seg
    seg.parent.mkdir(parents=True, exist_ok=True)
    dur, speed = float(shot["dur"]), float(shot.get("speed", 1.0))
    info = probe(path)
    iw, ih = info["width"], info["height"]
    c = dict(shot.get("crop") or {})
    if shot.get("zoom"):                                         # shorthand: zoom into a point
        z = shot["zoom"]; c = dict(hf=1.0 / float(z.get("factor", 1.5)), x=z.get("cx", 0.5), y=z.get("cy", 0.5))
    cw, ch, cx, cy = crop_box(iw, ih, W, H, c or {"hf": 1.0, "x": 0.5, "y": 0.5})
    needs_crop = (cw, ch) != (iw, ih)
    vf = []
    if kind == "video":
        ramp = shot.get("ramp")
        if ramp:
            a, b, r = ramp
            T = "(PTS-STARTPTS)*TB"
            vf.append(f"setpts='if(lt({T},{a}),{T}/{speed},if(lt({T},{b}),{a}/{speed}+({T}-{a})/{r},"
                      f"{a}/{speed}+({b}-{a})/{r}+({T}-{b})/{speed}))/TB'")
            read = dur * max(speed, 1.0, float(r)) + 1
        else:
            vf.append(f"setpts=(PTS-STARTPTS)/{speed}"); read = dur * speed
        vf.append(f"fps={FPS}")
    if needs_crop:
        vf.append(f"crop={cw}:{ch}:{cx}:{cy}")
    vf.append(f"scale={W}:{H}:flags=lanczos")
    n_frames = max(1, int(round(dur * FPS)))
    push = float(shot.get("push", 0) or 0)
    if push:                                                      # slow push-in on a still / locked shot
        z = f"(1+{push}*n/{n_frames})"
        vf.append(f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame:flags=bilinear,crop={W}:{H}")
    fx = shot.get("fx")
    if fx == "zoom":
        z = "(1+0.3*max(0,1-n/4))"
        vf.append(f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame:flags=bilinear,crop={W}:{H}")
    # colour -> PQ BT.2020 10-bit
    if color == "pq":
        vf.append("format=yuv422p10le")
    else:
        rng = "in_range=pc" if kind == "image" else "in_range=tv"
        vf.append(f"scale=in_color_matrix=bt709:{rng}:out_range=full" if kind == "video" else "format=gbrp16le")
        vf.append(to_pq_chain(color, luts))
    if fx == "flash":
        vf.append("fade=t=in:st=0:n=3:color=0x949494")            # lift to ~diffuse white, below HDR peak
    vf.append("setparams=colorspace=bt2020nc:color_primaries=bt2020:color_trc=smpte2084:range=tv")
    if kind == "image":
        inp = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", path]
    else:
        inp = ["-ss", str(shot["in"]), "-t", f"{read:.3f}", "-i", path]
    run(["ffmpeg", "-v", "error", "-y", *inp, "-an", "-vf", ",".join(vf), "-t", f"{dur:.3f}", "-r", str(FPS),
         "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
         "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc", "-color_range", "tv", seg])
    return seg


def font(size):
    for p, idx in (("/System/Library/Fonts/Avenir Next.ttc", 2), ("/System/Library/Fonts/Helvetica.ttc", 1), ("/Library/Fonts/Arial.ttf", 0)):
        try:
            return ImageFont.truetype(p, size, index=idx)
        except Exception:
            continue
    return ImageFont.load_default()


def make_overlay(text, path, level, W, H, y=330, size=84):
    k = W / 1080.0                                             # text geometry is authored for 1080 px width
    y, size = int(y * k), int(size * k)
    f, cx = font(size), W // 2
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).multiline_text((cx + int(3 * k), y + int(5 * k)), text, font=f, fill=(0, 0, 0, 200), anchor="mm", align="center", spacing=int(14 * k))
    sh = sh.filter(ImageFilter.GaussianBlur(10 * k))
    img = Image.alpha_composite(Image.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 0)), sh), sh)
    ImageDraw.Draw(img).multiline_text((cx, y), text, font=f, fill=(level, level, level, 255), anchor="mm", align="center", spacing=int(14 * k))
    img.save(path)


def final_pass(base, total, hdr, ctx, plan):
    W, H, FPS, WORK, SRC = ctx["W"], ctx["H"], ctx["FPS"], ctx["WORK"], ctx["SRC"]
    out_cfg = plan.get("output", {})
    fade = float(out_cfg.get("fade_out", 0.6))
    text = plan.get("text")
    name = plan["name"]
    out = SRC / (f"{name}_Reel.mp4" if (hdr or not ctx["hdr_main"]) else f"{name}_Reel_SDR.mp4")
    if ctx["preview"]:
        out = SRC / f"{name}_Reel_preview.mp4"
    lut = ctx["luts"]["pq2sdr"]
    tx_in, chain = [], ""
    if text and text.get("lines"):
        png = WORK / ("text_hdr.png" if hdr else "text_sdr.png")
        make_overlay(text["lines"], png, round(PQ_WHITE * 255) if hdr else 255, W, H, int(text.get("y", 330)), int(text.get("size", 84)))
        t0 = float(text.get("start", 0.3))
        fi, fo = f"fade=t=in:st={t0}:d=0.4:alpha=1", f"fade=t=out:st={total - fade - 0.3:.2f}:d=0.4:alpha=1"
        tx_in = ["-loop", "1", "-framerate", str(FPS), "-t", f"{total:.2f}", "-i", png]
        if hdr:
            chain = (f"[1:v]format=rgba,scale=in_range=full:out_range=tv:out_color_matrix=bt2020nc,format=yuva444p10le,{fi},{fo}[t];"
                     f"[0:v]format=yuv420p10le[b];[b][t]overlay=0:0:format=yuv420p10,fade=t=out:st={total - fade:.2f}:d={fade},format=yuv420p10le[v]")
        else:
            chain = (f"[1:v]format=rgba,{fi},{fo}[t];"
                     f"[0:v]scale=in_color_matrix=bt2020:in_range=tv:out_range=full,format=gbrp16le,lut3d=file={lut},"
                     f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[b];"
                     f"[b][t]overlay=0:0:format=yuv420,fade=t=out:st={total - fade:.2f}:d={fade},format=yuv420p,"
                     f"setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv[v]")
    else:
        if hdr:
            chain = f"[0:v]format=yuv420p10le,fade=t=out:st={total - fade:.2f}:d={fade},format=yuv420p10le[v]"
        else:
            chain = (f"[0:v]scale=in_color_matrix=bt2020:in_range=tv:out_range=full,format=gbrp16le,lut3d=file={lut},"
                     f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,fade=t=out:st={total - fade:.2f}:d={fade},"
                     f"setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv[v]")
    if hdr:
        mb = ctx["bitrate_mbps"]
        enc = ["-c:v", "hevc_videotoolbox", "-profile:v", "main10", "-b:v", f"{mb:g}M", "-maxrate", f"{mb * 1.5:g}M", "-tag:v", "hvc1", "-pix_fmt", "p010le",
               "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc", "-color_range", "tv"]
    else:
        mb = ctx["bitrate_mbps"]
        enc = ["-c:v", "libx264", "-crf", "14", "-maxrate", f"{mb * 1.5:g}M", "-bufsize", f"{mb * 3:g}M", "-preset", "slow", "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]
    audio_in = ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
    a_idx = 2 if tx_in else 1
    run(["ffmpeg", "-v", "error", "-y", "-i", base, *tx_in, *audio_in, "-filter_complex", chain, "-map", "[v]", "-map", f"{a_idx}:a",
         "-t", f"{total:.2f}", *enc, "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out])
    return out


def render_reel(plan, plan_path, only, no_sdr, preview=False):
    folder = Path(plan_path).resolve().parent.parent          # plan lives in <folder>/_work/plan.json
    SRC = folder
    WORK = folder / "_work"
    cfg = plan.get("output", {})
    res = resolve_output(plan, SRC)
    if preview:
        res.update(W=1080, H=1920, bitrate_mbps=16.0); no_sdr = True
    ctx = dict(W=res["W"], H=res["H"], FPS=res["FPS"], bitrate_mbps=res["bitrate_mbps"], preview=preview,
               SRC=SRC, WORK=WORK, luts=make_luts(WORK / "luts"), version="r5")
    shots = plan["shots"]
    if only:
        shots = [s for s in shots if s["id"] in only]
    segs = [render_segment(i, s, ctx) for i, s in enumerate(shots)]
    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs))
    base = WORK / "base_hdr.mov"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", base])
    total = sum(float(s["dur"]) for s in shots)
    any_hdr = any(source_kind(SRC / s["src"])[1] == "pq" for s in shots)
    hdr_cfg = cfg.get("hdr", "auto")
    ctx["hdr_main"] = any_hdr if hdr_cfg == "auto" else bool(hdr_cfg)
    outs = []
    if ctx["hdr_main"]:
        outs.append(final_pass(base, total, True, ctx, plan))
        if cfg.get("sdr_fallback", False) and not no_sdr:
            outs.append(final_pass(base, total, False, ctx, plan))
    else:
        outs.append(final_pass(base, total, False, ctx, plan))
    return outs, total, len(shots)


def render_product(plan, plan_path):
    folder = Path(plan_path).resolve().parent.parent
    p = plan["product"]; rem = SKILL / "remotion"
    if not (rem / "node_modules").exists():
        sys.exit("remotion deps missing: cd .agents/skills/video-edit/remotion && npm install")
    pub = rem / "public"; pub.mkdir(exist_ok=True)
    shutil.copy(folder / p["clip"], pub / Path(p["clip"]).name)
    cap = ""
    if p.get("captions"):
        sys.path.insert(0, str(Path(__file__).parent))
        from captions import transcribe
        model = REPO / "models" / "ggml-base.en.bin"
        out, n = transcribe(folder / p["clip"], model, pub / (Path(p["clip"]).stem + ".captions.json"))
        cap = out.name
    src_fps = (probe(folder / p["clip"]) or {}).get("fps", 30) or 30
    fps = min((24, 25, 30, 50, 60), key=lambda x: abs(x - src_fps))
    props = dict(fps=fps, hook=p.get("hook", ""), offer=p.get("offer", ""), clip=Path(p["clip"]).name, captionsFile=cap,
                 durationSec=float(p.get("duration", plan.get("brief", {}).get("target_sec", 12))))
    out = folder / f"{plan['name']}_Product.mp4"
    try:
        run(["npx", "remotion", "render", "src/index.ts", "ProductReel", out, f"--props={json.dumps(props)}",
             "--scale=2", "--crf=12", "--pixel-format=yuv420p"], cwd=rem)       # 2x of 1080x1920 = 4K, near-lossless H.264
    finally:                                                  # keep the template's public/ folder clean
        (pub / Path(p["clip"]).name).unlink(missing_ok=True)
        if cap:
            (pub / cap).unlink(missing_ok=True)
    return [out], props["durationSec"], 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan"); ap.add_argument("--only", default=""); ap.add_argument("--no-sdr", action="store_true")
    ap.add_argument("--preview", action="store_true", help="1080x1920 draft for quick review")
    a = ap.parse_args()
    plan = read_json(a.plan)
    if plan.get("type", "reel") == "product":
        outs, total, n = render_product(plan, a.plan)
    else:
        outs, total, n = render_reel(plan, a.plan, set(filter(None, a.only.split(","))), a.no_sdr, a.preview)
    info = probe(outs[0])
    print(json.dumps({"outputs": [str(o) for o in outs], "duration": round(total, 2), "shots": n,
                      "resolution": f"{info['width']}x{info['height']}", "fps": info["fps"]}))
