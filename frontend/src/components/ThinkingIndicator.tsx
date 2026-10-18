"use client";

import { useEffect, useState } from "react";

import { Avatar } from "./MessageView";

const PHASES = [
  "Thinking",
  "Understanding your question",
  "Choosing the right workflow",
  "Working with your data",
  "Preparing the answer",
];
const PHASE_SECONDS = 3;

export default function ThinkingIndicator() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);

  const phase = Math.min(PHASES.length - 1, Math.floor(seconds / PHASE_SECONDS));

  return (
    <article className="mb-7 flex animate-message-in gap-3" aria-label="Data Agent is working">
      <Avatar role="assistant" className="animate-avatar-pulse" />
      <div className="min-w-0 flex-1">
        <div className="mb-1 text-xs font-medium text-muted-foreground">Data Agent</div>
        <div className="flex min-h-6 items-center gap-2.5 text-sm">
          <span className="inline-flex gap-1" aria-hidden="true">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="size-[7px] animate-dot-bounce rounded-full bg-primary"
                style={{ animationDelay: `${dot * 0.15}s` }}
              />
            ))}
          </span>
          {/* key restarts the fade-in each time the phase changes */}
          <span key={phase} className="animate-in duration-300 fade-in slide-in-from-bottom-1">
            <span className="animate-shimmer bg-linear-to-r from-muted-foreground via-foreground to-muted-foreground bg-size-[200%_100%] bg-clip-text text-transparent">
              {PHASES[phase]}
            </span>
          </span>
          {seconds > 0 && (
            <span className="text-xs text-muted-foreground tabular-nums">{seconds}s</span>
          )}
        </div>
      </div>
    </article>
  );
}
