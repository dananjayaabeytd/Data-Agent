"use client";

import { Bot, User } from "lucide-react";
import { useEffect, useEffectEvent, useMemo, useState } from "react";

import type { ChatMessage, Role } from "@/lib/api";
import { usePrefersReducedMotion } from "@/lib/hooks";
import { cn } from "@/lib/utils";
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

export function Avatar({ role, className }: { role: Role; className?: string }) {
  return (
    <div
      className={cn(
        "grid size-8 shrink-0 place-items-center rounded-lg",
        role === "user" ? "bg-secondary text-secondary-foreground" : "bg-primary/15 text-primary",
        className,
      )}
    >
      {role === "user" ? <User className="size-4" /> : <Bot className="size-4" />}
    </div>
  );
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
    <article className={cn("mb-7 flex gap-3", message.animate && "animate-message-in")}>
      <Avatar role={message.role} />
      <div className="min-w-0 flex-1 wrap-anywhere">
        <div className="mb-1 text-xs font-medium text-muted-foreground">{isUser ? "You" : "Data Agent"}</div>
        {isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{text}</p>
        ) : (
          <Markdown text={text} className={typing ? "typing-caret" : undefined} />
        )}
      </div>
    </article>
  );
}
