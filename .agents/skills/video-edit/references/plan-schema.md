# plan.json reference (`video-edit/plan@1`)

Lives at `<folder>/_work/plan.json`. Edit it, then `plan.py validate`, `plan.py show`, `render.py`. `templates/plan.example.json` is a worked example.

```jsonc
{
  "schema": "video-edit/plan@1", "type": "reel",          // "reel" (ffmpeg) | "product" (Remotion)
  "name": "Trip",                                         // output: <folder>/Trip_Reel.mp4 (one file; + Trip_Reel_SDR.mp4 only if sdr_fallback is true)
  "brief": { "goal": "...", "platform": "instagram_reel", "target_sec": 30, "text_line": null,
             "music": "added in app (silent output)", "hero": "s1", "ending": "s9", "notes": [] },
  "output": { "width": 2160, "height": 3840, "fps": "auto", "hdr": "auto", "sdr_fallback": false, "fade_out": 0.6, "silent": true },   // 4K default; fps "auto" = highest source fps (<= 60); optional "bitrate_mbps"
  "text": { "lines": "POV: you escape\nto the hills", "start": 0.3, "y": 330, "size": 84 },     // or null; ONE line for the whole video
  "music": { "track": null, "snap_every": null },
  "shots": [ { "id": "s1", "src": "clip.mp4", "in": 5.5, "dur": 3.5, "speed": 1.0, "rationale": "hook: ...", "approved": false } ],
  "constraints": { "max_dur": 35, "avg_shot": [1.2, 3.2], "match_direction": true, "no_end_on_camera_turn": true },
  "decisions": [ { "q": "text line?", "a": "none", "by": "user" } ]
}
```

## Shot fields
| field | meaning |
|---|---|
| `id`, `src` | unique id; file name inside the folder (video, HEIC, JPG, PNG) |
| `in`, `dur` | video: source start seconds and OUTPUT length. Stills: `dur` only |
| `speed` | playback speed (0.25-8). `dur` is output seconds, so the source consumed is `dur*speed` |
| `ramp` | `[a, b, s]`: source seconds a..b (from the shot start) play at `s`x, the rest at `speed` (slow-mo hit / whoosh) |
| `fx` | `"flash"` (3-frame lift on the cut INTO the shot) or `"zoom"` (4-frame punch-in); use on beats, sparingly |
| `crop` | `{x, y, hf}`: window of height `hf*H` (9:16 shaped) at fractional position x,y within the source. Reframes landscape clips, drops watermarks/strangers from photos |
| `zoom` | shorthand `{factor, cx, cy}` = crop with `hf=1/factor`; centre from `peek.py --centroid` for a lit subject on a dark scene |
| `push` | slow push-in over the shot (`0.04` = 4 %), mainly for stills |
| `rationale` | REQUIRED one line: why this shot, why here |
| `approved` | user signed off: do not change |

Colour handling is automatic per source: PQ HDR stays as is; SDR video and photos are mapped into PQ with LUTs (P3 matrix for HEIC).

## Validation (`plan.py validate`)
Errors (exit 1): missing source/rationale, bad ids/fx/ramp/speed, window past the end of the clip, `max_dur` exceeded.
Warnings: hard cut inside a window, face in window, soft/shaky source, messenger photo without crop, near-duplicates both used,
average shot outside range, all shots the same length, a sub-0.5 s shot, long first shot, long text, empty goal, nothing approved.
`--fix` snaps `in`/`dur` to the frame grid (fps).

## Product plans
`"type": "product", "product": {"clip": "file.mp4", "hook": "...", "offer": "...", "captions": true, "duration": 12}`; see `product-playbook.md`.
