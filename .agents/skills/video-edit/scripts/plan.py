#!/usr/bin/env python
"""STEPS 2-3 of the video-edit skill: draft, validate and tweak the edit plan (plan.json).

  plan.py draft    <folder> [--target 30] [--type reel] [--name Trip]   auto-draft from the analysis map (a STARTING POINT)
  plan.py validate <folder>/_work/plan.json [--fix]                     checks; --fix snaps times to the frame grid
  plan.py snap     <plan.json> --track song.mp3 [--every 2]             snap shot lengths to a beat grid (timing only)
  plan.py show     <plan.json>                                          one-line-per-shot table (dry run)

The plan is the single source of truth: change shots here, never in ffmpeg commands. Each shot needs a `rationale`;
`approved: true` shots are locked in by the user and must not be changed. See references/plan-schema.md.
Exit code 1 when validation finds errors. Output is JSON on stdout.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vlib import read_json, write_json, probe

SCHEMA = "video-edit/plan@1"
FX = {None, "flash", "zoom"}


def load_map(folder):
    mp = Path(folder) / "_work" / "analysis" / "map.json"
    if not mp.exists():
        sys.exit(f"no analysis map at {mp}. Run analyze.py first.")
    return read_json(mp)


def draft(folder, target, ptype, name):
    folder = Path(folder).resolve()
    m = load_map(folder)
    name = name or folder.name.capitalize()
    dup_drop = {d["b"] for d in m["duplicates"]}
    rows = []
    for c in m["clips"]:
        ag = c.get("agent") or {}
        if ag.get("use") == "skip" or c["id"] in dup_drop or "undecodable_or_empty" in c["flags"]:
            continue
        if not c["candidates"]:
            continue
        best = c["candidates"][0]
        rows.append((c, best, ag))
    rows.sort(key=lambda r: (not r[2].get("hero"), r[0]["probe"].get("created") or "", r[0]["file"]))
    shots, total, k = [], 0.0, 0
    for c, best, ag in rows:
        if total >= target:
            break
        k += 1
        if c["kind"] == "image":
            dur = 1.2
            sh = dict(id=f"s{k}", src=c["file"], dur=dur, push=0.04)
        else:
            L = best["end"] - best["start"]
            dur = round(min(L, 3.0 if c["probe"]["duration"] > 6 else 2.0), 2)
            sh = dict(id=f"s{k}", src=c["file"], **{"in": round(best["start"], 2)}, dur=dur, speed=1.0)
        sh.update(rationale=f"auto-draft: best window of {c['id']} (score {best['score']}; {', '.join(best['why']) or 'n/a'})"
                  + (f"; flags {best['flags']}" if best["flags"] else ""), approved=False, fx=None, crop=None)
        shots.append(sh); total += dur
    plan = dict(schema=SCHEMA, type=ptype, name=name,
                brief=dict(goal=None, platform="instagram_reel", target_sec=target, text_line=None, music="added in app (silent output)",
                           hero=None, ending=None, notes=[]),
                output=dict(width=2160, height=3840, fps="auto", hdr="auto", sdr_fallback=False, fade_out=0.6, silent=True),
                text=None, music=dict(track=None, snap_every=None), shots=shots,
                constraints=dict(max_dur=target + 5, avg_shot=[1.2, 3.2], match_direction=True, no_end_on_camera_turn=True),
                decisions=[], status="draft")
    out = folder / "_work" / "plan.json"
    write_json(out, plan)
    print(json.dumps(dict(plan=str(out), shots=len(shots), duration=round(total, 2),
                          note="DRAFT: review the contact sheets, reorder, set hook/ending, add rationale, then validate")))


def frame_snap(t, fps):
    return round(round(float(t) * fps) / fps, 4)


def validate(path, fix=False):
    plan = read_json(path); folder = Path(path).resolve().parent.parent
    errors, warnings = [], []
    from vlib import resolve_output
    fps = resolve_output(plan, folder)["FPS"]
    shots = plan.get("shots", [])
    if plan.get("type", "reel") == "product":
        p = plan.get("product") or {}
        if not (folder / p.get("clip", "")).exists():
            errors.append(f"product.clip not found: {p.get('clip')}")
        return report(errors, warnings, {}, path)
    if not shots:
        errors.append("no shots")
    amap = None
    mp = folder / "_work" / "analysis" / "map.json"
    if mp.exists():
        amap = {c["file"]: c for c in read_json(mp)["clips"]}
    seen, ids, total, durs = {}, set(), 0.0, []
    changed = False
    for i, s in enumerate(shots):
        sid = s.get("id", f"#{i}")
        if sid in ids: errors.append(f"{sid}: duplicate id")
        ids.add(sid)
        if not s.get("rationale"): errors.append(f"{sid}: rationale is required (why this shot, why here)")
        src = folder / s.get("src", "")
        if not src.is_file():
            errors.append(f"{sid}: source missing: {s.get('src')}"); continue
        dur = float(s.get("dur", 0)); speed = float(s.get("speed", 1.0))
        if dur <= 0: errors.append(f"{sid}: dur must be > 0")
        if not 0.25 <= speed <= 8: errors.append(f"{sid}: speed {speed} outside 0.25..8")
        if s.get("fx") not in FX: errors.append(f"{sid}: fx must be one of flash|zoom|null")
        if s.get("ramp"):
            r = s["ramp"]
            if len(r) != 3 or not (0 <= r[0] < r[1]): errors.append(f"{sid}: ramp must be [a, b, speed] with 0<=a<b")
        is_img = src.suffix.lower() in (".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp")
        if not is_img:
            if "in" not in s: errors.append(f"{sid}: video shot needs 'in'")
            else:
                info = probe(src)
                need = float(s["in"]) + dur * speed
                if info["duration"] and need > info["duration"] + 0.05:
                    errors.append(f"{sid}: in+dur*speed = {need:.2f}s exceeds the clip ({info['duration']:.2f}s)")
                if fix:
                    s["in"] = frame_snap(s["in"], fps)
            if amap and s["src"] in amap:
                c = amap[s["src"]]
                a, b = float(s["in"]), float(s["in"]) + dur * speed
                if any(a < t < b for t in c.get("cut_times", [])):
                    warnings.append(f"{sid}: window {a:.1f}-{b:.1f}s contains a hard cut inside the source clip")
                faces = c.get("timeline", {}).get("faces", [])
                tt = c.get("timeline", {}).get("t", [])
                if any(a - 0.5 <= t <= b + 0.5 and n > 0 for t, n in zip(tt, faces)):
                    warnings.append(f"{sid}: a face was detected in this window: check bystander / privacy by eye")
                if "soft_or_blurry_vs_folder" in c.get("flags", []):
                    warnings.append(f"{sid}: clip is soft relative to the rest of the folder")
                segs = [x["camera"] for x in c.get("camera_segments", []) if x["start"] < b and x["end"] > a]
                if "handheld_shaky" in segs: warnings.append(f"{sid}: shaky camera inside the window")
        elif amap and s["src"] in amap:
            c = amap[s["src"]]
            if "faces_possible" in c["flags"]: warnings.append(f"{sid}: face possible in photo: check privacy")
            if "messenger_export_soft_or_watermarked" in c["flags"] and not s.get("crop"):
                warnings.append(f"{sid}: messenger export without a crop: corner watermark may show")
        if fix:
            s["dur"] = max(1 / fps, frame_snap(dur, fps)); changed = True
        seen.setdefault(s["src"], []).append(sid)
        total += float(s["dur"]); durs.append(float(s["dur"]))
    for src, sh in seen.items():
        if len(sh) > 1 and not all((x.get("src") != src or x.get("in") is not None) for x in shots):
            pass
        if len(sh) > 1:
            warnings.append(f"{src} used {len(sh)}x ({', '.join(sh)}): fine for stills/bursts, check variety")
    if amap:
        for d in read_json(mp).get("duplicates", []):
            a = next((c["file"] for c in read_json(mp)["clips"] if c["id"] == d["a"]), None)
            b = next((c["file"] for c in read_json(mp)["clips"] if c["id"] == d["b"]), None)
            if a in seen and b in seen:
                warnings.append(f"near-duplicates both used: {a} and {b}")
    cst = plan.get("constraints", {}); br = plan.get("brief", {})
    tgt = float(br.get("target_sec") or 0)
    if tgt and total > tgt * 1.25: warnings.append(f"total {total:.1f}s is >25% over the {tgt:.0f}s target")
    if cst.get("max_dur") and total > cst["max_dur"]: errors.append(f"total {total:.1f}s exceeds max_dur {cst['max_dur']}")
    if durs:
        avg = sum(durs) / len(durs)
        lo, hi = cst.get("avg_shot", [1.2, 3.2])
        if not lo <= avg <= hi: warnings.append(f"average shot length {avg:.2f}s outside {lo}-{hi}s")
        if len(durs) > 4 and (max(durs) - min(durs)) < 0.3: warnings.append("all shots nearly the same length: pacing will feel flat, vary it")
        if min(durs) < 0.5: warnings.append("a shot is shorter than 0.5s: only OK on a beat/flash cut")
    if shots and shots[0].get("dur", 0) > 4: warnings.append("first shot is long: the hook should land in the first 1-3s")
    t = plan.get("text")
    if t and t.get("lines") and len(t["lines"]) > 60: warnings.append("text line is long: keep a POV-style line short (<= 2 lines)")
    if not plan.get("brief", {}).get("goal"): warnings.append("brief.goal is empty: confirm goal/platform with the user")
    if not any(s.get("approved") for s in shots): warnings.append("no shot is approved yet (ask the user to approve the cut before rendering)")
    if fix and changed:
        write_json(path, plan)
    return report(errors, warnings, dict(shots=len(shots), duration=round(total, 2), avg_shot=round(sum(durs) / len(durs), 2) if durs else 0), path)


def report(errors, warnings, stats, path):
    print(json.dumps(dict(plan=str(path), ok=not errors, errors=errors, warnings=warnings, stats=stats), indent=1))
    sys.exit(1 if errors else 0)


def snap(path, track, every):
    from beats import beat_grid, snap_durations
    plan = read_json(path)
    shots = plan["shots"]
    locked = [s for s in shots if s.get("approved")]
    if locked: print(f"note: {len(locked)} approved shots will also be re-timed; re-confirm with the user", file=sys.stderr)
    tempo, beats, cuts = beat_grid(track, every)
    new = snap_durations([float(s["dur"]) for s in shots], cuts)
    for s, d in zip(shots, new):
        s["dur"] = d
    plan["music"] = dict(track=str(track), snap_every=every, tempo_bpm=round(tempo, 1))
    write_json(path, plan)
    print(json.dumps(dict(tempo_bpm=round(tempo, 1), durations=new, total=round(sum(new), 2))))


def show(path):
    plan = read_json(path); t = 0.0
    print(f"{plan.get('name')}  type={plan.get('type', 'reel')}  target={plan.get('brief', {}).get('target_sec')}s  text={plan.get('text')}")
    for s in plan.get("shots", []):
        d = float(s["dur"])
        extra = " ".join(f"{k}={s[k]}" for k in ("speed", "ramp", "fx", "crop", "zoom", "push") if s.get(k) not in (None, 1.0, 0))
        print(f"{t:6.2f}-{t + d:6.2f}  {s['id']:<4} {s['src']:<34} in={s.get('in', '-')!s:<6} dur={d:<5} {extra} {'[APPROVED]' if s.get('approved') else ''}\n         why: {s.get('rationale', '')[:110]}")
        t += d
    print(f"total {t:.2f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft"); d.add_argument("folder"); d.add_argument("--target", type=float, default=30)
    d.add_argument("--type", default="reel", choices=["reel", "product"]); d.add_argument("--name")
    v = sub.add_parser("validate"); v.add_argument("plan"); v.add_argument("--fix", action="store_true")
    n = sub.add_parser("snap"); n.add_argument("plan"); n.add_argument("--track", required=True); n.add_argument("--every", type=int, default=2)
    w = sub.add_parser("show"); w.add_argument("plan")
    a = ap.parse_args()
    if a.cmd == "draft": draft(a.folder, a.target, a.type, a.name)
    elif a.cmd == "validate": validate(a.plan, a.fix)
    elif a.cmd == "snap": snap(a.plan, a.track, a.every)
    else: show(a.plan)
