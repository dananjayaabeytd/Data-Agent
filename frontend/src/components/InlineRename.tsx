"use client";

import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface Props {
  initial: string;
  className?: string;
  onSubmit: (title: string) => void;
  onCancel: () => void;
}

export default function InlineRename({ initial, className, onSubmit, onCancel }: Props) {
  const [value, setValue] = useState(initial);
  const inputRef = useRef<HTMLInputElement>(null);
  const finished = useRef(false);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const commit = () => {
    if (finished.current) return;
    finished.current = true;
    const title = value.trim();
    if (title && title !== initial) onSubmit(title);
    else onCancel();
  };

  return (
    <Input
      ref={inputRef}
      className={cn("h-8 border-primary/60 font-medium", className)}
      value={value}
      maxLength={120}
      aria-label="Session title"
      onChange={(event) => setValue(event.target.value)}
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
        } else if (event.key === "Escape") {
          finished.current = true;
          onCancel();
        }
      }}
      onBlur={commit}
    />
  );
}
