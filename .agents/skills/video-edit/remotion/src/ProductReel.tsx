import React, { useEffect, useState } from "react";
import {
  AbsoluteFill, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
  delayRender, continueRender,
} from "remotion";
import type { Caption } from "@remotion/captions";

export type ProductReelProps = {
  hook: string; offer: string; clip: string; captionsFile: string; durationSec: number; fps: number;
};

// Instagram UI covers ~250px at the top and ~350px at the bottom of a 1080x1920 reel.
const SAFE_TOP = 250, SAFE_BOTTOM = 350;
const font = '"Avenir Next", "Helvetica Neue", Arial, sans-serif';

const Hook: React.FC<{ text: string }> = ({ text }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const pop = spring({ frame: f, fps, config: { damping: 12 } });
  const out = interpolate(f, [fps * 2.4, fps * 2.8], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", top: SAFE_TOP + 40, left: 60, right: 60, textAlign: "center",
      color: "white", fontFamily: font, fontWeight: 800, fontSize: 88, lineHeight: 1.1, whiteSpace: "pre-line",
      textShadow: "0 4px 24px rgba(0,0,0,.65)", transform: `scale(${0.6 + 0.4 * pop})`, opacity: out * pop }}>
      {text}
    </div>
  );
};

// Tear-through reveal: footage starts zoomed + blurred, then a wipe snaps it sharp (slow, then fast).
const Reveal: React.FC<{ clip: string; durationInFrames: number }> = ({ clip, durationInFrames }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = interpolate(f, [0, fps * 1.6], [0, 1], { extrapolateRight: "clamp" });
  const eased = t * t * t;                               // slow start, fast end
  const blur = interpolate(eased, [0, 1], [28, 0]);
  const scale = interpolate(eased, [0, 1], [1.25, 1]);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ filter: `blur(${blur}px)`, transform: `scale(${scale})` }}>
        <OffthreadVideo src={staticFile(clip)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Offer: React.FC<{ text: string }> = ({ text }) => {
  const f = useCurrentFrame(); const { fps, durationInFrames } = useVideoConfig();
  const start = durationInFrames - fps * 2.5;
  const p = spring({ frame: f - start, fps, config: { damping: 14 } });
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: SAFE_BOTTOM + 40, textAlign: "center",
      fontFamily: font, fontWeight: 800, fontSize: 72, color: "white", opacity: Math.max(0, p),
      transform: `translateY(${(1 - Math.max(0, p)) * 60}px)`, textShadow: "0 4px 24px rgba(0,0,0,.65)" }}>
      <span style={{ background: "rgba(0,0,0,.55)", padding: "14px 34px", borderRadius: 18 }}>{text}</span>
    </div>
  );
};

// Word-by-word captions: the current word is highlighted.
const Captions: React.FC<{ file: string }> = ({ file }) => {
  const [caps, setCaps] = useState<Caption[] | null>(null);
  const [handle] = useState(() => delayRender("captions"));
  useEffect(() => {
    fetch(staticFile(file)).then((r) => r.json()).then((c) => { setCaps(c); continueRender(handle); })
      .catch(() => continueRender(handle));
  }, [file, handle]);
  const { fps } = useVideoConfig(); const ms = (useCurrentFrame() / fps) * 1000;
  if (!caps) return null;
  const i = caps.findIndex((c) => ms >= c.startMs && ms < c.endMs + 150);
  if (i < 0) return null;
  const page = caps.slice(Math.max(0, i - 2), i + 3);      // a window of 5 words around the current one
  return (
    <div style={{ position: "absolute", left: 60, right: 60, bottom: SAFE_BOTTOM + 260, textAlign: "center",
      fontFamily: font, fontWeight: 800, fontSize: 70, lineHeight: 1.15, textShadow: "0 4px 20px rgba(0,0,0,.7)" }}>
      {page.map((c, k) => {
        const on = caps.indexOf(c) === i;
        return <span key={k} style={{ color: on ? "#ffe14d" : "white", transform: on ? "scale(1.08)" : "none",
          display: "inline-block", margin: "0 16px" }}>{c.text.trim()}</span>;
      })}
    </div>
  );
};

export const ProductReel: React.FC<ProductReelProps> = ({ hook, offer, clip, captionsFile }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const fade = interpolate(useCurrentFrame(), [durationInFrames - fps * 0.5, durationInFrames], [1, 0],
    { extrapolateLeft: "clamp" });
  return (
    <AbsoluteFill style={{ background: "black", opacity: fade }}>
      <Reveal clip={clip} durationInFrames={durationInFrames} />
      <Hook text={hook} />
      {captionsFile ? <Captions file={captionsFile} /> : null}
      <Offer text={offer} />
    </AbsoluteFill>
  );
};
