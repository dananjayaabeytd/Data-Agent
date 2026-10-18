"use client";

import { useEffect, useEffectEvent, useMemo, useState } from "react";

import type { ChatMessage } from "@/lib/api";
import { usePrefersReducedMotion } from "@/lib/hooks";
import Markdown from "./Markdown";

export type UiMessage = ChatMessage & {
  id: string;
  animate?: boolean; // slide in when first shown
  reveal?: boolean; // type the text out word by word
};

interface Props {
  message: UiMessage;
  onRevealDone: (id: string) => void;
  onProgress: () => void;
}

// Reveals text word by word, capped so long answers still finish quickly.
function useRevealedText(text: string, enabled: boolean, onDone: () => void, onProgress: () => void) {
  const tokens = useMemo(() => text.split(/(\s+)/), [text]);
  const [count, setCount] = useState(enabled ? 0 : tokens.length);
  const done = useEffectEvent(onDone);
  const progress = useEffectEvent(onProgress);

  useEffect(() => {
    if (!enabled) return;
    const duration = Math.min(1600, Math.max(350, tokens.length * 18));
    const started = performance.now();
    let frame = requestAnimationFrame(function step(now) {
      const target = Math.min(tokens.length, Math.ceil(((now - started) / duration) * tokens.length));
      setCount(target);
      progress();
      if (target < tokens.length) frame = requestAnimationFrame(step);
      else done();
    });
    return () => cancelAnimationFrame(frame);
  }, [enabled, tokens]);

  const finished = !enabled || count >= tokens.length;
  return { text: finished ? text : tokens.slice(0, count).join(""), typing: !finished };
}

export default function MessageView({ message, onRevealDone, onProgress }: Props) {
  const reduceMotion = usePrefersReducedMotion();
  const isUser = message.role === "user";
  const { text, typing } = useRevealedText(
    message.content,
    Boolean(message.reveal) && !reduceMotion,
    () => onRevealDone(message.id),
    onProgress,
  );

  return (
    <article className={`message ${message.role}${message.animate ? " enter" : ""}`}>
      <div className="avatar">{isUser ? "YOU" : "AI"}</div>
      <div className="message-body">
        <div className="message-role">{isUser ? "You" : "Data Agent"}</div>
        <div className={`message-content${typing ? " typing" : ""}`}>
          {isUser ? <p className="plain">{text}</p> : <Markdown text={text} />}
        </div>
      </div>
    </article>
  );
}
