"use client";

import type { SessionSummary } from "@/lib/api";

interface Props {
  sessions: SessionSummary[];
  activeId: string | null;
  disabled: boolean;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

function timeAgo(iso: string): string {
  const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60_000);
  if (Math.abs(minutes) < 60) return relative.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return relative.format(hours, "hour");
  return relative.format(Math.round(hours / 24), "day");
}

export default function Sidebar({ sessions, activeId, disabled, onNew, onSelect, onDelete }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">D</span>
        <strong>Data Agent</strong>
      </div>
      <button className="new-session" type="button" onClick={onNew}>
        + New chat
      </button>
      <div className="section-label">Sessions</div>
      <nav className="sessions" aria-label="Saved sessions">
        {sessions.length === 0 && <p className="sessions-empty">No sessions yet</p>}
        {sessions.map((session) => (
          <div
            key={session.session_id}
            className={`session${session.session_id === activeId ? " active" : ""}`}
          >
            <button className="session-open" type="button" onClick={() => onSelect(session.session_id)}>
              <strong>{session.title}</strong>
              <small>
                {session.message_count} messages · {timeAgo(session.updated_at)}
              </small>
            </button>
            <button
              className="session-delete"
              type="button"
              aria-label={`Delete ${session.title}`}
              title="Delete session"
              disabled={disabled}
              onClick={() => onDelete(session.session_id)}
            >
              ×
            </button>
          </div>
        ))}
      </nav>
    </aside>
  );
}
