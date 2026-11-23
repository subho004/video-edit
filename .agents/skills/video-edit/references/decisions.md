# Decisions: what to ask, what to default to

Ask in ONE round, as a short numbered list with a proposed default for each, so the user can answer "ok" or change a few.
Use your environment's ask-the-user tool if it has one, otherwise plain chat. Skip anything already answered. If you cannot
ask (non-interactive), pick the default, write it in `plan.json -> decisions` with `by: "default"` and list it in the report.

## Always (unless known)
| Question | Default to propose |
|---|---|
| Goal and platform? (reel, short, product teaser, demo, recap) | Instagram Reel, 9:16. Export master is always 4K (2160x3840) at the highest source fps; do not ask about resolution |
| Target length? | 20-35 s for travel/montage; 10-20 s product teaser; 20-45 s demo |
| Text on screen? One POV-style line, a hook for a product, or none | none for pure scenery; one short POV line if the user wants a hook. Never per-shot labels or CTAs unless asked |
| Music? | Added later in the app: output stays silent. If the user supplies a track: use it for beat timing only |
| Hero shot / how should it end? | Hero = best-scored candidate marked by you; end on a calm wide shot, never on someone turning to the camera |
| Anything to avoid or must include? | Strangers' faces, plates, signs, specific shots |

## Ask only when the map shows it
| Trigger in map.json / footage | Question |
|---|---|
| `faces_possible` | Which faces are the subject vs bystanders? Keep, crop out, or drop those shots? |
| `near-duplicates` | Which one to keep? (default: the sharper / the one with the better candidate window) |
| `long_clip_pick_sections` | Which moments or sections matter? Show candidates from the sheets and let the user name them |
| `*_needs_reframe` (landscape/square) | Where should the 9:16 crop sit (left/centre/right, tighter zoom)? Offer two crops if unsure |
| Mixed HDR + SDR | Fine by default (HDR main file, SDR mapped in). Mention only if an SDR clip looks poor next to HDR (offer to drop it) |
| `soft_or_blurry_vs_folder`, `shaky`, `dark` | Use briefly, or skip? Default: skip unless it is the only coverage |
| Messenger-export photos/clips | Use briefly, crop the corner watermark, or skip? |
| Photos taken where photography is restricted (signs seen in frames) | Ask before including them |
| Speech in a clip (`audio.level` normal/loud) | Is the speech wanted (captions) or should it be muted as usual? |
| Several walking shots | Which direction/orientation should lead? (match direction of travel at cuts) |
| Style reference ("like trending reels") | Beat-synced cuts? speed ramps? flashes/zooms? Offer 2-3 concrete options from `styles.md` |

## Do NOT ask
Technical choices (codec, bitrate, LUTs, crop maths), things with a sensible convention, or anything the user already decided.
When unsure between two valid options, make the pick, name it in one line, and say it can be swapped in one edit.

## After the cut is drafted (Gate 2)
Show: shot table, total length vs target, what was left out and why, assumptions. Ask: "approve, or what to change?".
Interpret the user's shorthand and state the interpretation (e.g. "front view" = forward-facing POV shot; "my walking shot" = the shot with
the user in frame walking; "replace with a moving clip" = choose a high-motion shot).
