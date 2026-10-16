// Bars that move with the loudness of the microphone, shown in the microphone button while it records,
// so the candidate sees that the voice arrives (the text only appears after the transcription).
// Like CallView, it reads audio.ts (meter) in its own animation loop instead of re-rendering React.
import { useEffect, useRef } from "react";
import { meter } from "../audio";

const BARS = [0.6, 1, 0.8, 1, 0.6]; // the middle bars move most

export default function MicWave() {
  const bars = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    let frame = 0;
    let level = 0;
    const draw = () => {
      level = level * 0.7 + meter.mic * 0.3; // smooth, so the bars do not flicker
      bars.current.forEach((bar, i) => {
        if (bar) bar.style.transform = `scaleY(${0.2 + 0.8 * Math.min(1, level * BARS[i] * (1 + 0.3 * Math.sin(performance.now() / 120 + i)))})`;
      });
      frame = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <span className="flex h-5 items-center gap-0.5" aria-hidden="true">
      {BARS.map((_, i) => (
        <span
          key={i}
          ref={(el) => {
            bars.current[i] = el;
          }}
          className="h-5 w-1 origin-center rounded-full bg-current"
          style={{ transform: "scaleY(0.2)" }}
        />
      ))}
    </span>
  );
}
