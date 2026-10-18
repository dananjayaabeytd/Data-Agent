"use client";

import { useEffect, useState } from "react";

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
    <article className="message assistant thinking enter" aria-label="Data Agent is working">
      <div className="avatar">AI</div>
      <div className="message-body">
        <div className="message-role">Data Agent</div>
        <div className="thinking-line">
          <span className="dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          {/* key restarts the fade-in animation each time the phase changes */}
          <span key={phase} className="thinking-label">
            {PHASES[phase]}
          </span>
          {seconds > 0 && <span className="thinking-time">{seconds}s</span>}
        </div>
      </div>
    </article>
  );
}
