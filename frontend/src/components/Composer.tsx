"use client";

import { useEffect, useRef } from "react";

interface Props {
  value: string;
  busy: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export default function Composer({ value, busy, onChange, onSubmit }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Grow with the content, up to the CSS max-height.
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [value]);

  useEffect(() => {
    if (!busy) textareaRef.current?.focus();
  }, [busy]);

  return (
    <div className="composer-wrap">
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          placeholder="Ask about your data, an API, or a transformation..."
          aria-label="Message"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
        />
        <button className="send" type="submit" disabled={busy || !value.trim()}>
          {busy ? <span className="spinner" aria-label="Working" /> : "Send"}
        </button>
      </form>
      <div className="composer-hint">Enter to send · Shift+Enter for a new line</div>
    </div>
  );
}
