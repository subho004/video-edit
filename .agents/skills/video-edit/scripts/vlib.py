"""Shared helpers for the video-edit scripts: subprocess, ffprobe, colour LUTs, paths, JSON IO."""
import hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np

SKILL = Path(__file__).resolve().parent.parent
REPO = SKILL.parents[2]            # <repo>/.agents/skills/video-edit -> <repo>
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts", ".3gp"}
IMAGE_EXT = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".dng"}


def run(cmd, check=True, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if check and r.returncode:
        sys.exit(f"command failed: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-2500:]}")
    return r


def probe(path):
    """ffprobe summary. Dimensions are DISPLAY dimensions (rotation applied)."""
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path])
    j = json.loads(r.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    if not v:
        return None
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
    rot = rot or int((v.get("tags") or {}).get("rotate", 0) or 0)
    if abs(rot) % 180 == 90:
        w, h = h, w

    def fr(x):
        try:
            n, d = x.split("/"); return float(n) / float(d) if float(d) else 0.0
        except Exception:
            return 0.0
    trc = v.get("color_transfer", "")
    dur = float(v.get("duration") or j["format"].get("duration") or 0)
    return {
        "codec": v["codec_name"], "pix_fmt": v.get("pix_fmt"), "width": w, "height": h, "rotation": rot,
        "orientation": "portrait" if h > w else "landscape" if w > h else "square",
        "duration": round(dur, 3), "fps": round(fr(v.get("avg_frame_rate", "0/1")), 3),
        "vfr": abs(fr(v.get("avg_frame_rate", "0/1")) - fr(v.get("r_frame_rate", "0/1"))) > 0.5,
        "color_transfer": trc, "color_primaries": v.get("color_primaries", ""), "color_space": v.get("color_space", ""),
        "hdr": trc in ("smpte2084", "arib-std-b67"), "transfer_pq": trc == "smpte2084", "bit_depth": 10 if "10" in (v.get("pix_fmt") or "") else 8,
        "has_audio": a is not None, "audio_codec": a["codec_name"] if a else None,
        "size_mb": round(int(j["format"].get("size", 0)) / 1e6, 1),
        "created": (j["format"].get("tags") or {}).get("creation_time"),
    }


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False))


def read_json(path):
    return json.loads(Path(path).read_text())


def md5(*parts, n=8):
    return hashlib.md5(repr(parts).encode()).hexdigest()[:n]


# ---------------------------------------------------------------- colour LUTs (65^3 .cube)
def _pq_eotf(e):
    m1 = 2610 / 16384; m2 = 2523 / 4096 * 128; c1 = 3424 / 4096; c2 = 2413 / 4096 * 32; c3 = 2392 / 4096 * 32
    p = np.clip(e, 0, 1) ** (1 / m2)
    return 10000 * (np.maximum(p - c1, 0) / (c2 - c3 * p)) ** (1 / m1)


def _pq_oetf(nits):
    m1 = 2610 / 16384; m2 = 2523 / 4096 * 128; c1 = 3424 / 4096; c2 = 2413 / 4096 * 32; c3 = 2392 / 4096 * 32
    y = np.clip(nits / 10000, 0, 1) ** m1
    return ((c1 + c2 * y) / (1 + c3 * y)) ** m2


_M2020_FROM_709 = np.array([[0.6274, 0.3293, 0.0433], [0.0691, 0.9195, 0.0114], [0.0164, 0.0880, 0.8956]])
_M2020_FROM_P3 = np.array([[0.7538, 0.1986, 0.0476], [0.0457, 0.9418, 0.0125], [-0.0012, 0.0176, 0.9836]])
_M709_FROM_2020 = np.array([[1.6605, -0.5876, -0.0728], [-0.1246, 1.1329, -0.0083], [-0.0182, -0.1006, 1.1187]])


def _write_cube(path, out, n=65):
    with open(path, "w") as f:
        f.write(f"LUT_3D_SIZE {n}\n")
        for o in out:
            f.write("%.6f %.6f %.6f\n" % tuple(o))


def _grid(n=65):
    g = np.linspace(0, 1, n)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")          # cube order: red fastest
    return np.stack([r, gg, b], -1).reshape(-1, 3)


def make_luts(dirpath):
    """pq2sdr (HDR -> SDR tone-map, for fallback + analysis), sdr709_to_pq / sdrP3_to_pq (SDR -> HDR file)."""
    d = Path(dirpath); d.mkdir(parents=True, exist_ok=True)
    out = {k: d / f"{k}.cube" for k in ("pq2sdr", "sdr709_to_pq", "sdrP3_to_pq")}
    rgb = _grid()
    if not out["pq2sdr"].exists():
        lin = np.clip((_pq_eotf(rgb) / 203.0 * 0.85) @ _M709_FROM_2020.T, 0, None)
        L = lin @ np.array([.2126, .7152, .0722])
        Lt = L * (1 + L / 16.0) / (1 + L)                    # extended Reinhard on luminance
        o = np.clip(lin * np.where(L > 1e-6, Lt / np.maximum(L, 1e-6), 1)[:, None], 0, 1)
        _write_cube(out["pq2sdr"], np.where(o < 0.0031308, 12.92 * o, 1.055 * o ** (1 / 2.4) - 0.055))
    for name, M in (("sdr709_to_pq", _M2020_FROM_709), ("sdrP3_to_pq", _M2020_FROM_P3)):
        if not out[name].exists():
            lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)    # sRGB EOTF
            nits = np.clip(lin @ M.T, 0, 1) * 203.0                                         # diffuse white = 203 nits
            _write_cube(out[name], _pq_oetf(nits))
    return out


# ffmpeg filter fragments (applied to a yuv frame that has been scaled already)
def tonemap_to_rgb24(lut):
    return (f"scale=in_color_matrix=bt2020:in_range=tv:out_range=full,format=gbrp16le,"
            f"lut3d=file={lut},format=rgb24")


def folder_media(folder):
    folder = Path(folder)
    vids = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and not p.name.startswith(".")
                  and not any(k in p.stem for k in ("_Reel", "_Product")))
    imgs = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT and not p.name.startswith("."))
    return vids, imgs


STD_FPS = (24, 25, 30, 50, 60)


def resolve_output(plan, folder):
    """-> dict(W, H, FPS, bitrate_mbps) with defaults: 4K (2160x3840), fps = the highest source fps (snapped to a standard rate, max 60)."""
    cfg = plan.get("output", {})
    W, H = int(cfg.get("width", 2160)), int(cfg.get("height", 3840))
    fps = cfg.get("fps", "auto")
    if fps in (None, "auto"):
        best = 0.0
        for s in plan.get("shots", []):
            p = Path(folder) / s.get("src", "")
            if p.suffix.lower() in VIDEO_EXT and p.exists():
                try:
                    best = max(best, (probe(p) or {}).get("fps", 0.0))
                except SystemExit:
                    pass
        fps = min(STD_FPS, key=lambda x: abs(x - best)) if best else 30
        fps = min(fps, 60)
    fps = int(fps)
    br = cfg.get("bitrate_mbps")
    if br is None:
        br = round(min(120, 55 * (W * H) / (2160 * 3840) * fps / 30 * (1 if W * H >= 2160 * 3840 else 1.6)), 1)
        br = max(br, 8)
    return dict(W=W, H=H, FPS=fps, bitrate_mbps=float(br))
