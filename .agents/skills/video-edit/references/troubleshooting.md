# Troubleshooting

| Symptom | Cause / fix |
|---|---|
| SDR file plays dark / ffprobe says smpte2084 | PQ tag leaked: the chain must end with `setparams=...bt709`. Re-render; `verify.py` flags it |
| `analyze.py` : cv2 FaceDetector assertion | detector shared across threads or sizes: already locked; if you edit, keep one detector per size under a lock |
| HEIC fails | `sips` missing (non-macOS): convert to PNG first (ImageMagick/libheif) |
| Photo orientation wrong | sips keeps the EXIF tag; ffmpeg autorotates PNG/JPG, so crop AFTER rotation (render does) |
| Flash looks blown out in HDR | `fx:"flash"` uses 0x949494; if sources are very dim lower it in render.py |
| Cache not refreshing | segments are keyed by shot + source size/mtime + render version; bump `version` in `render.py` or delete `<folder>/_work/segments` |
| Two shots the same look | check `duplicates` in map.json and `plan.py validate` warnings |
| Text too low/high | `text.y` (default 330 of 1920), keep inside safe zones; <= 22 chars per line at size 84 |
| `read_raw` returns nothing | seek beyond clip end, or hw decode failure: scripts retry without `-hwaccel`; check `ffprobe` duration |
| Remotion render times out first time | headless Chrome downloads on the first run: retry |
| `zsh` loop `for s in $x` does not split | zsh does not word-split unquoted variables: use arrays |
| macOS sed | `sed -i ''` needs the empty string |
| Parallel ffmpeg jobs | use `&` + `wait` in a bash loop (xargs + nested quoting breaks); lavfi/audio inputs go BEFORE `-filter_complex`/`-map` |
| Python `hash()` cache misses | randomised per run: use `vlib.md5` |
