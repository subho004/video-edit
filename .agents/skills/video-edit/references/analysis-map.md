# analysis map (map.json) reference

Produced by `analyze.py <folder>` -> `<folder>/_work/analysis/map.json`. Schema id `video-edit/analysis-map@1`.

## Top level
`summary` (counts, total video seconds, hdr clip count) · `clips[]` · `duplicates[]` (`a`,`b` clip ids, Hamming `distance` <= 8 of 64-bit dHash)
· `decisions_needed[]` (plain-language hints) · `how_to_read`.

## clips[]
| field | meaning |
|---|---|
| `id`, `file`, `kind` | `c01`..; file name; `video` or `image` |
| `probe` | display width/height (rotation applied), orientation, duration, fps, `vfr`, codec, `color_transfer`, `hdr`, audio presence, size_mb, created |
| `sampling` | how frames were sampled: `fps=1/step` or `keyframes` (clips > 6 min) |
| `metrics` | `sharp_median`, `sharp_p10` (Laplacian variance at 640 px: compare ONLY within the folder), `brightness_mean`, `clip_frac` (blown), `dark_frac`, `motion_energy_mean`, `faces_max`, `face_h_max` |
| `timeline` | per-sample arrays `t`, `sharp`, `bright`, `faces` |
| `camera_segments[]` | runs of `static`, `gentle`, `moving` (walk / subject motion), `pan_left/right`, `tilt_up/down`, `handheld_shaky`, `cut` with start/end seconds. Pan direction = which way the CAMERA turns |
| `scenes`, `cut_times` | hard cuts inside the clip (PySceneDetect for clips <= 5 min + motion pass) |
| `candidates[]` | up to 6 non-overlapping windows (`start`,`end`,`score` 0-1,`why`,`flags`) ranked by sharpness x exposure x steadiness x interest minus face/cut/softness penalties |
| `audio` | `mean_db`,`max_db`,`level` (silent/quiet/normal/loud) |
| `flags` | `hdr`, `vfr`, `low_res`, `dark`, `blown_highlights`, `faces_possible`, `shaky`, `soft_or_blurry_vs_folder`, `long_clip_pick_sections`, `very_short`, `landscape_needs_reframe`, `messenger_export_soft_or_watermarked`, `display_p3_source` (HEIC), `undecodable_or_empty` |
| `sheet` | contact sheet path relative to `_work/analysis/` |
| `agent` | **filled by you** after viewing: `subject`, `shot_type` (wide/medium/detail/back/pov/…), `use` (hook/body/ending/skip/unset), `hero` (bool), `privacy` (notes), `notes` |

## Reliability (be honest about it)
- Scores are cheap local heuristics: good at flagging blur, shake, blown/dark frames, duplicates; **not** at taste or story. The agent decides.
- Faces: YuNet at 640 px finds clear faces; misses small, masked, profile ones. "No faces" is not a privacy guarantee. Plates and text are not detected: look.
- Motion classes use 5 fps phase correlation on 160 px frames; thresholds are tuned for handheld phone footage. Forward walking shows as `moving`.
- Clips > 4 min get motion on 24 probe windows only. Photos have one candidate.
- HLG (`arib-std-b67`) sources are not tone-mapped in sheets (they look flat); PQ is.

## Annotating
After viewing a sheet, write to the clip's `agent` block in map.json (edit the JSON). Re-running analyze keeps those blocks. Use `use: "skip"`
to exclude a clip from `plan.py draft`; `hero: true` to start the draft with it.
