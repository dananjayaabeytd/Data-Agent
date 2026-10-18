"use client";

import { Eraser, FileJson, FileText, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ExportFormat } from "@/lib/export";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  busy: boolean;
  className?: string;
  align?: "start" | "end";
  onRename: () => void;
  onExport: (format: ExportFormat) => void;
  onClear: () => void;
  onDelete: () => void;
}

export default function SessionActions({
  label,
  busy,
  className,
  align = "end",
  onRename,
  onExport,
  onClear,
  onDelete,
}: Props) {
  // Keep focus in the rename input instead of letting the menu return it to the trigger.
  const renaming = useRef(false);

  return (
    // Non-modal so opening the confirm dialog from an item never leaves the page inert.
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`Actions for ${label}`}
          className={cn("text-muted-foreground data-[state=open]:bg-accent data-[state=open]:text-foreground", className)}
        >
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={align}
        className="w-52"
        onCloseAutoFocus={(event) => {
          if (renaming.current) {
            event.preventDefault();
            renaming.current = false;
          }
        }}
      >
        <DropdownMenuItem
          onSelect={() => {
            renaming.current = true;
            onRename();
          }}
        >
          <Pencil />
          Rename
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => onExport("md")}>
          <FileText />
          Download as Markdown
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => onExport("json")}>
          <FileJson />
          Download as JSON
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={busy} onSelect={onClear}>
          <Eraser />
          Clear messages
        </DropdownMenuItem>
        <DropdownMenuItem variant="destructive" disabled={busy} onSelect={onDelete}>
          <Trash2 />
          Delete session
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
