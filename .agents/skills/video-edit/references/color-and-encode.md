# Colour, HDR and encoding (read when touching render.py or debugging colour)

## Source facts
Phone clips: 4K HEVC 10-bit HDR10 (PQ / BT.2020), portrait via a rotation matrix that ffmpeg autorotates. Raw contact sheets look flat/dark
because PQ is shown as SDR: tone-map for VIEWING only (analysis does this with `pq2sdr.cube`; sheets get a x1.15 gamma lift; output never does).
Some inputs are SDR: HEIC photos (Display-P3), JPG/PNG exports (sRGB), low-res messenger videos (H.264 BT.709). HLG sources are not handled by the PQ LUT.

## ffmpeg build limits (typical Homebrew build)
No `zscale`, `drawtext`, `libx265`. Available: `lut3d`, `overlay`, `prores_ks`, `hevc_videotoolbox` (macOS), `libx264`. So: text is a PIL PNG overlay;
tone-mapping and SDR->HDR use `.cube` LUTs generated with numpy (`vlib.make_luts`); HDR encode uses VideoToolbox.

## Output quality (always)
Default is 4K portrait **2160x3840** at the **highest source fps** (snapped to 24/25/30/50/60, max 60: Instagram accepts up to 60) and a high bitrate:
HEVC VideoToolbox main10 at ~55 Mb/s per 30 fps (110 Mb/s at 60), max 1.5x; SDR fallback x264 `-preset slow -crf 14 -profile high` capped at the same ceiling. Override with `output.width/height/fps/bitrate_mbps`
only when the user asks. Mixed 30/60 sources render at 60 (30 fps clips repeat frames; 60 fps sources give smoother ramps/slow-mo). 1080p or photo sources are upscaled with lanczos;
the platform will re-compress and may downscale, but the user wants a master. ProRes 422 HQ segments cost ~50 MB per second at 4K. Text geometry (size/y) is authored for 1080 px and scaled automatically.
`render.py --preview` makes a 1080x1920 draft (16 Mb/s, separate cache) for fast review only.

## Pipeline (render.py)
Per shot: `-ss` (before `-i`) -> `setpts` speed/ramp -> `fps` -> optional crop -> `scale 1080x1920 lanczos` -> optional push/zoom/flash -> colour map -> ProRes 422 10-bit
`.mov` tagged bt2020/smpte2084 (cache key = md5 of the shot + source size/mtime + render version). Then concat demuxer `-c copy` -> ONE final encode:
`hevc_videotoolbox -profile main10 -b:v <bitrate> -tag:v hvc1 -pix_fmt p010le` with `-color_primaries bt2020 -color_trc smpte2084 -colorspace bt2020nc -color_range tv`,
silent AAC from `anullsrc`, end fade 0.6 s. Pixels of HDR sources pass through untouched (verified: mean Y within 0.2 of the source).

## SDR sources into the HDR file
`format=gbrp16le` -> `lut3d` (`sdr709_to_pq`, or `sdrP3_to_pq` for HEIC): sRGB EOTF -> primaries matrix to BT.2020 -> x203 nits -> PQ OETF -> `scale=out_color_matrix=bt2020nc:out_range=tv,format=yuv422p10le`.
SDR video: `scale=in_color_matrix=bt709:in_range=tv:out_range=full` first. A dark/grainy 1080p SDR clip still looks poor next to HDR: drop it rather than force it.

## SDR fallback (OFF by default; only when `output.sdr_fallback: true` or the user asks)
`pq2sdr.cube`: PQ EOTF -> nits/203 x 0.85 -> BT.2020->709 matrix -> extended Reinhard on luminance (white point 4) -> sRGB OETF; `libx264 -crf 19`, bt709, yuv420p.
**The chain must end with `setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv`**, otherwise the PQ tag leaks, the file is labelled HDR and plays
dark. Frame dumps ignore tags: only `ffprobe` shows it. Check BOTH files (`verify.py` does).

## Text in HDR
PIL full-frame transparent PNG with blurred shadow; for HDR pre-scale the white to the PQ signal of 203-nit diffuse white (0.5807 x 255 = 148); convert with
`format=rgba,scale=in_range=full:out_range=tv:out_color_matrix=bt2020nc,format=yuva444p10le`, fade with `alpha=1`, `overlay=format=yuv420p10`. Plain 255 white is blinding in HDR.
Font: Avenir Next Demi Bold (`/System/Library/Fonts/Avenir Next.ttc`, index 2; index 1 is Bold *Italic*). ~42 px per char at 84 px: keep lines <= ~22 chars.

## Flash / zoom / ramp
`flash` = `fade in n=3 color=0x949494` (about diffuse white; kept below peak so it does not blind). `zoom` = frame-eval `scale` + `crop` over 4 frames. `ramp` = piecewise `setpts`.
Slow-mo (<1x) duplicates frames at 30 fps (no interpolation): keep slow hits short.

## Checks
`ffprobe -show_entries stream=color_transfer,color_primaries,pix_fmt,codec_tag_string`; audio `ffmpeg -i f -vn -af volumedetect -f null -` -> `max_volume: -91.0 dB` = silent.
Output size at 4K: ~7 MB per second of video (30 s reel ~ 200 MB).
