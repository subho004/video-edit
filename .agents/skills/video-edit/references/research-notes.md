# Research notes (why the skill is built this way)

Pipeline pattern (JSON checkpoints: probe -> analyse -> plan -> audit -> approval gate -> render -> verify the render), model picks IDs from a map not raw
timestamps, labelled contact-sheet grids coarse-to-fine, required per-shot rationale, deterministic validation before render, verify the output file with
`not_measured` = fail: github.com/logsv/llm-video-editor, github.com/agamm/video-agent, github.com/social-media-skills/video-editing-skill,
github.com/mrpaidsocial/mrpaidsocial-video-editor-agent, github.com/anato13/cutagent, ffmpeg-skill (github.com/kajisho5/ffmpeg-skill).
Portable skill format: agentskills.io/specification (name = folder, description <= 1024 chars, SKILL.md < 500 lines, scripts/references/assets, JSON output + --help scripts);
discovery dirs: `.agents/skills` (Codex, Cursor, Gemini, opencode, Copilot, Windsurf) and `.claude/skills` (Claude Code; also read by Cursor/opencode/Copilot/Cline). AGENTS.md is the cross-tool file; CLAUDE.md = `@AGENTS.md`.
Analysis methods: Laplacian variance relative to the clip median, 5 fps phase-correlation camera motion, YuNet faces (OpenCV zoo), dHash duplicates, keyframe-only sampling
(`-skip_frame nokey`), contact sheet + agent eyes beats small local VLMs. Aesthetic scorers (LAION/CLIP) are optional tie-breakers only (heavy, biased to stock photos).
Tools: librosa beat_track (cut every 2nd/4th beat, min gap ~0.35 s), PySceneDetect, whisper.cpp word timestamps -> Remotion captions (`@remotion/captions`), Remotion template-tiktok.
Caveats: trend/duration claims come from marketing blogs and conflict (7-15 s vs 30-60 s best reach); star counts are unverified; tools were not benchmarked here.
