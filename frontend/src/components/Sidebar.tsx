"use client";

import { Plus, Search } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { SessionSummary } from "@/lib/api";
import type { ExportFormat } from "@/lib/export";
import { cn } from "@/lib/utils";
import InlineRename from "./InlineRename";
import SessionActions from "./SessionActions";

interface Props {
  sessions: SessionSummary[];
  activeId: string | null;
  pendingSessionId: string | null;
  busy: boolean;
  renamingId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onRenameStart: (id: string) => void;
  onRenameSubmit: (id: string, title: string) => void;
  onRenameCancel: () => void;
  onExport: (id: string, format: ExportFormat) => void;
  onClear: (id: string) => void;
  onDelete: (id: string) => void;
  onDeleteMany: (ids: string[]) => Promise<boolean>;
  onDeleteAll: () => void;
}

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const DAY_MS = 86_400_000;

function timeAgo(iso: string): string {
  const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60_000);
  if (Math.abs(minutes) < 60) return relative.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return relative.format(hours, "hour");
  return relative.format(Math.round(hours / 24), "day");
}

function groupLabel(iso: string): string {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const day = new Date(iso);
  day.setHours(0, 0, 0, 0);
  const days = Math.round((startOfToday.getTime() - day.getTime()) / DAY_MS);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Previous 7 days";
  if (days < 30) return "Previous 30 days";
  return "Older";
}

// Sessions arrive sorted by updated_at (newest first), so groups come out in order.
function groupSessions(sessions: SessionSummary[]) {
  const groups: { label: string; items: SessionSummary[] }[] = [];
  for (const session of sessions) {
    const label = groupLabel(session.updated_at);
    const last = groups.at(-1);
    if (last?.label === label) last.items.push(session);
    else groups.push({ label, items: [session] });
  }
  return groups;
}

export default function Sidebar(props: Props) {
  const { sessions, activeId, pendingSessionId, busy, renamingId } = props;
  const [query, setQuery] = useState("");
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const term = query.trim().toLowerCase();
  const visible = term ? sessions.filter((s) => s.title.toLowerCase().includes(term)) : sessions;
  const visibleIds = visible.map((s) => s.session_id);
  const selectedVisible = visibleIds.filter((id) => selected.has(id));
  const allSelected = visibleIds.length > 0 && selectedVisible.length === visibleIds.length;

  const exitSelecting = () => {
    setSelecting(false);
    setSelected(new Set());
  };

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const deleteSelected = async () => {
    if (await props.onDeleteMany(selectedVisible)) exitSelecting();
  };

  return (
    <aside className="flex min-h-0 flex-col gap-3 border-b bg-sidebar p-4 text-sidebar-foreground max-md:max-h-[40dvh] md:border-r md:border-b-0">
      <div className="flex items-center gap-2.5 px-1.5">
        <span className="grid size-8 place-items-center rounded-lg bg-primary font-extrabold text-primary-foreground">
          D
        </span>
        <strong className="tracking-wide">Data Agent</strong>
      </div>

      <Button size="lg" className="w-full font-semibold" onClick={props.onNew}>
        <Plus />
        New chat
      </Button>

      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          placeholder="Search sessions"
          aria-label="Search sessions"
          className="pl-8"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {selecting ? (
        <div className="flex min-h-7 items-center gap-2 px-1.5 text-xs">
          <label className="flex cursor-pointer items-center gap-2">
            <Checkbox
              checked={allSelected}
              onCheckedChange={() => setSelected(allSelected ? new Set() : new Set(visibleIds))}
              aria-label="Select all"
            />
            All
          </label>
          <span className="flex-1 text-muted-foreground">{selectedVisible.length} selected</span>
          <Button
            variant="destructive"
            size="xs"
            disabled={busy || selectedVisible.length === 0}
            onClick={deleteSelected}
          >
            Delete
          </Button>
          <Button variant="ghost" size="xs" onClick={exitSelecting}>
            Cancel
          </Button>
        </div>
      ) : (
        <div className="flex min-h-7 items-center gap-1 px-1.5">
          <span className="flex-1 text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase">
            Sessions · {sessions.length}
          </span>
          <Button variant="ghost" size="xs" disabled={sessions.length === 0} onClick={() => setSelecting(true)}>
            Select
          </Button>
          <Button
            variant="ghost"
            size="xs"
            className="text-destructive hover:text-destructive"
            disabled={busy || sessions.length === 0}
            onClick={props.onDeleteAll}
          >
            Delete all
          </Button>
        </div>
      )}

      <nav className="-mx-1 flex min-h-0 flex-col gap-3 overflow-y-auto px-1" aria-label="Saved sessions">
        {sessions.length === 0 && <p className="px-1.5 text-sm text-muted-foreground">No sessions yet</p>}
        {sessions.length > 0 && visible.length === 0 && (
          <p className="px-1.5 text-sm text-muted-foreground">No sessions match “{query.trim()}”</p>
        )}
        {groupSessions(visible).map((group) => (
          <div key={group.label} className="flex flex-col gap-0.5">
            <div className="px-2.5 py-1 text-[11px] font-semibold text-muted-foreground">{group.label}</div>
            {group.items.map((session) => {
              const id = session.session_id;
              const isActive = id === activeId && !selecting;
              const isSelected = selected.has(id);

              return (
                <div
                  key={id}
                  className={cn(
                    "group/session flex items-center rounded-lg transition-colors hover:bg-sidebar-accent has-data-[state=open]:bg-sidebar-accent",
                    isActive && "bg-sidebar-accent",
                    isSelected && "bg-primary/10 hover:bg-primary/15",
                  )}
                >
                  {selecting && (
                    <Checkbox
                      className="ml-2.5"
                      checked={isSelected}
                      onCheckedChange={() => toggle(id)}
                      aria-label={`Select ${session.title}`}
                    />
                  )}
                  {renamingId === id ? (
                    <div className="min-w-0 flex-1 p-1.5">
                      <InlineRename
                        initial={session.title}
                        onSubmit={(title) => props.onRenameSubmit(id, title)}
                        onCancel={props.onRenameCancel}
                      />
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="flex min-w-0 flex-1 flex-col items-start gap-0.5 rounded-lg px-2.5 py-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                      onClick={() => (selecting ? toggle(id) : props.onSelect(id))}
                      onDoubleClick={() => !selecting && props.onRenameStart(id)}
                    >
                      <span className="flex w-full items-center gap-1.5 text-sm font-medium">
                        {pendingSessionId === id && (
                          <span className="size-[7px] shrink-0 animate-pulse-dot rounded-full bg-primary" aria-label="Working" />
                        )}
                        <span className="truncate">{session.title}</span>
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {session.message_count} messages · {timeAgo(session.updated_at)}
                      </span>
                    </button>
                  )}
                  {!selecting && renamingId !== id && (
                    <SessionActions
                      label={session.title}
                      busy={busy}
                      className={cn(
                        "mr-1 opacity-0 group-hover/session:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100 max-md:opacity-100",
                        isActive && "opacity-100",
                      )}
                      onRename={() => props.onRenameStart(id)}
                      onExport={(format) => props.onExport(id, format)}
                      onClear={() => props.onClear(id)}
                      onDelete={() => props.onDelete(id)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}
