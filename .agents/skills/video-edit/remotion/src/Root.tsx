import { Composition } from "remotion";
import { ProductReel, ProductReelProps } from "./ProductReel";

// Edit these defaults (or pass --props='{"hook":"..."}' to `remotion render`).
// Put footage in remotion/public/ and reference it by file name; put captions.json from
// `scripts/captions.py` there too (leave captionsFile empty for a silent product reel).
const defaults: ProductReelProps = {
  hook: "Meet the one thing\nyou'll use every day",
  offer: "Now available",
  clip: "product.mp4",          // remotion/public/product.mp4 (portrait or landscape; it is cover-fitted)
  captionsFile: "",             // e.g. "talk.captions.json"
  durationSec: 12,
  fps: 30,                      // set to the source frame rate (render.py does this automatically)
};

export const Root = () => (
  <Composition
    id="ProductReel"
    component={ProductReel}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={defaults.durationSec * 30}
    defaultProps={defaults}
    calculateMetadata={({ props }) => ({ durationInFrames: Math.round(props.durationSec * props.fps), fps: props.fps })}
  />
);
