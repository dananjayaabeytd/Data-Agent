"use client";

import { Loader2, SendHorizontal } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";

interface Props {
  value: string;
  busy: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export default function Composer({ value, busy, onChange, onSubmit }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Grow with the content, up to the max height.
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
    <div className="px-4 pt-3 pb-5 md:px-7" data-print-hide>
      <form
        className="mx-auto flex w-full max-w-[900px] gap-2 rounded-xl border bg-card p-2 transition-[border-color,box-shadow] focus-within:border-primary/50 focus-within:ring-3 focus-within:ring-primary/15"
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
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2.5 py-2.5 text-sm outline-none placeholder:text-muted-foreground"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
        />
        <Button type="submit" size="lg" className="self-end px-3.5" disabled={busy || !value.trim()}>
          {busy ? (
            <Loader2 className="animate-spin" aria-label="Working" />
          ) : (
            <>
              <SendHorizontal />
              Send
            </>
          )}
        </Button>
      </form>
      <div className="mx-auto mt-1.5 max-w-[900px] text-right text-[11px] text-muted-foreground">
        Enter to send · Shift+Enter for a new line
      </div>
    </div>
  );
}
