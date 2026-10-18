"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api, type ChatMessage, type SessionSummary } from "@/lib/api";
import { downloadSession, type ExportFormat } from "@/lib/export";
import { usePrefersReducedMotion } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import Composer from "./Composer";
import ConfirmDialog, { type ConfirmOptions } from "./ConfirmDialog";
import InlineRename from "./InlineRename";
import MessageView, { type UiMessage } from "./MessageView";
import SessionActions from "./SessionActions";
import Sidebar from "./Sidebar";
import ThinkingIndicator from "./ThinkingIndicator";

const NEW_CHAT_TITLE = "New chat";
const SUGGESTIONS = [
  "What payment methods are available?",
  "Which 3 cities have the most users?",
  "What are the most common reasons rides get cancelled?",
  "Extract data from https://pokeapi.co/api/v2/pokemon and save it to data/extract as csv",
];

type Place = "sidebar" | "header";

function toUiMessages(sessionId: string, messages: ChatMessage[]): UiMessage[] {
  return messages.map((message, index) => ({ ...message, id: `${sessionId}-${index}` }));
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong";
}

function sessionTitle(message: string): string {
  const title = message.replace(/\s+/g, " ").trim();
  return title.length > 60 ? `${title.slice(0, 57)}...` : title;
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function StatusPill({ busy }: { busy: boolean }) {
  return (
    <div
      role="status"
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs text-muted-foreground transition-colors",
        busy && "border-primary/40 bg-primary/10 text-foreground",
      )}
    >
      <span className={cn("size-2 rounded-full bg-primary", busy && "animate-pulse-dot")} />
      <span className={busy ? "ellipsis" : undefined}>{busy ? "Working" : "Ready"}</span>
    </div>
  );
}

export default function ChatApp() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [title, setTitle] = useState(NEW_CHAT_TITLE);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Which view a request is pending in. Views change when the user switches sessions,
  // so a late response never lands in the wrong conversation.
  const [view, setView] = useState(0);
  const [pendingView, setPendingView] = useState<number | null>(null);
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<{ id: string; place: Place } | null>(null);
  const [confirmOptions, setConfirmOptions] = useState<ConfirmOptions | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const confirmResolver = useRef<((confirmed: boolean) => void) | null>(null);
  const viewRef = useRef(0);
  const nextId = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const reduceMotion = usePrefersReducedMotion();

  const pending = pendingView !== null;
  const pendingHere = pendingView === view;

  const confirm = useCallback(
    (options: ConfirmOptions) =>
      new Promise<boolean>((resolve) => {
        confirmResolver.current?.(false);
        confirmResolver.current = resolve;
        setConfirmOptions(options);
        setConfirmOpen(true);
      }),
    [],
  );

  const settleConfirm = useCallback((confirmed: boolean) => {
    confirmResolver.current?.(confirmed);
    confirmResolver.current = null;
    setConfirmOpen(false);
  }, []);

  const refreshSessions = useCallback(async () => {
    setSessions(await api.listSessions());
  }, []);

  const showView = useCallback((sessionId: string | null, viewTitle: string, viewMessages: UiMessage[]) => {
    viewRef.current += 1;
    setView(viewRef.current);
    setActiveId(sessionId);
    setTitle(viewTitle);
    setMessages(viewMessages);
    setError(null);
  }, []);

  const openSession = useCallback(
    async (sessionId: string) => {
      try {
        const session = await api.getSession(sessionId);
        showView(session.session_id, session.title, toUiMessages(session.session_id, session.messages));
      } catch (caught) {
        setError(errorText(caught));
      }
    },
    [showView],
  );

  const newChat = useCallback(() => showView(null, NEW_CHAT_TITLE, []), [showView]);

  useEffect(() => {
    (async () => {
      try {
        const list = await api.listSessions();
        setSessions(list);
        if (list.length) await openSession(list[0].session_id);
      } catch (caught) {
        setError(errorText(caught));
      }
    })();
  }, [openSession]);

  const isNearBottom = () => {
    const element = scrollRef.current;
    return !element || element.scrollHeight - element.scrollTop - element.clientHeight < 160;
  };

  const scrollToBottom = useCallback(
    (smooth = true) => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: smooth && !reduceMotion ? "smooth" : "auto",
      });
    },
    [reduceMotion],
  );

  useEffect(() => scrollToBottom(false), [view, scrollToBottom]);
  useEffect(() => scrollToBottom(), [messages.length, pendingHere, scrollToBottom]);

  const followReveal = useCallback(() => {
    if (isNearBottom()) scrollToBottom(false);
  }, [scrollToBottom]);

  const finishReveal = useCallback((id: string) => {
    setMessages((current) => current.map((m) => (m.id === id ? { ...m, reveal: false } : m)));
  }, []);

  // Runs a session action, reporting failures as a toast.
  async function run(action: () => Promise<void>) {
    try {
      await action();
    } catch (caught) {
      toast.error(errorText(caught));
    }
  }

  const titleOf = (sessionId: string) =>
    sessions.find((session) => session.session_id === sessionId)?.title ?? "this session";

  async function send(text: string) {
    const message = text.trim();
    if (!message || pending) return;

    const requestView = viewRef.current;
    const userMessage: UiMessage = {
      id: `local-${nextId.current++}`,
      role: "user",
      content: message,
      animate: true,
    };
    setError(null);
    setDraft("");
    setPendingView(requestView);
    setPendingSessionId(activeId);
    setMessages((current) => [...current, userMessage]);

    try {
      let sessionId = activeId;
      if (!sessionId) {
        const created = await api.createSession(sessionTitle(message));
        sessionId = created.session_id;
        setPendingSessionId(sessionId);
        refreshSessions().catch(() => undefined);
        if (viewRef.current === requestView) {
          setActiveId(created.session_id);
          setTitle(created.title);
        }
      }
      const result = await api.sendMessage(sessionId, message);
      if (viewRef.current === requestView) {
        setMessages((current) => [
          ...current,
          {
            id: `local-${nextId.current++}`,
            role: "assistant",
            content: result.answer,
            animate: true,
            reveal: true,
          },
        ]);
      }
    } catch (caught) {
      if (viewRef.current === requestView) {
        // The API saves messages only on success, so roll back the optimistic one.
        setMessages((current) => current.filter((m) => m.id !== userMessage.id));
        setDraft((current) => current || message);
        setError(errorText(caught));
      }
    } finally {
      setPendingView(null);
      setPendingSessionId(null);
      refreshSessions().catch(() => undefined);
    }
  }

  const renameSession = (sessionId: string, newTitle: string) =>
    run(async () => {
      setRenaming(null);
      const session = await api.renameSession(sessionId, newTitle);
      setSessions((current) =>
        current.map((s) => (s.session_id === sessionId ? { ...s, title: session.title } : s)),
      );
      if (sessionId === activeId) setTitle(session.title);
      toast.success("Session renamed");
    });

  const clearSession = (sessionId: string) =>
    run(async () => {
      const ok = await confirm({
        title: "Clear messages?",
        message: `All messages in “${titleOf(sessionId)}” will be removed. The session itself is kept.`,
        confirmLabel: "Clear messages",
        danger: true,
      });
      if (!ok) return;
      await api.clearSession(sessionId);
      if (sessionId === activeId) setMessages([]);
      await refreshSessions();
      toast.success("Messages cleared");
    });

  const deleteSession = (sessionId: string) =>
    run(async () => {
      const ok = await confirm({
        title: "Delete session?",
        message: `“${titleOf(sessionId)}” and all its messages will be permanently deleted.`,
        confirmLabel: "Delete",
        danger: true,
      });
      if (!ok) return;
      await api.deleteSession(sessionId);
      if (sessionId === activeId) newChat();
      await refreshSessions();
      toast.success("Session deleted");
    });

  async function deleteSessions(sessionIds: string[]): Promise<boolean> {
    let deleted = false;
    await run(async () => {
      const ok = await confirm({
        title: `Delete ${plural(sessionIds.length, "session")}?`,
        message: "The selected sessions and all their messages will be permanently deleted.",
        confirmLabel: "Delete selected",
        danger: true,
      });
      if (!ok) return;
      const result = await api.deleteSessions(sessionIds);
      if (activeId && sessionIds.includes(activeId)) newChat();
      await refreshSessions();
      toast.success(`${plural(result.deleted, "session")} deleted`);
      deleted = true;
    });
    return deleted;
  }

  const deleteAllSessions = () =>
    run(async () => {
      const ok = await confirm({
        title: "Delete all sessions?",
        message: `All ${plural(sessions.length, "session")} and their messages will be permanently deleted. This cannot be undone.`,
        confirmLabel: "Delete all",
        danger: true,
      });
      if (!ok) return;
      const result = await api.deleteAllSessions();
      newChat();
      await refreshSessions();
      toast.success(`${plural(result.deleted, "session")} deleted`);
    });

  const exportSession = (sessionId: string, format: ExportFormat) =>
    run(async () => {
      downloadSession(await api.getSession(sessionId), format);
    });

  const headerRenaming = renaming?.place === "header" && renaming.id === activeId;

  return (
    <div className="grid h-dvh grid-rows-[auto_1fr] md:grid-cols-[280px_1fr] md:grid-rows-1">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        pendingSessionId={pendingSessionId}
        busy={pending}
        renamingId={renaming?.place === "sidebar" ? renaming.id : null}
        onNew={newChat}
        onSelect={openSession}
        onRenameStart={(id) => setRenaming({ id, place: "sidebar" })}
        onRenameSubmit={renameSession}
        onRenameCancel={() => setRenaming(null)}
        onExport={exportSession}
        onClear={clearSession}
        onDelete={deleteSession}
        onDeleteMany={deleteSessions}
        onDeleteAll={deleteAllSessions}
      />

      <main className="flex min-h-0 min-w-0 flex-col">
        <header className="flex min-h-16 items-center justify-between gap-4 border-b px-5 md:min-h-[76px] md:px-8">
          <div className="min-w-0">
            <div className="text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase">
              Unified data workspace
            </div>
            {headerRenaming && activeId ? (
              <InlineRename
                className="mt-0.5 max-w-md text-base"
                initial={title}
                onSubmit={(newTitle) => renameSession(activeId, newTitle)}
                onCancel={() => setRenaming(null)}
              />
            ) : activeId ? (
              <h1 className="mt-0.5 truncate text-lg font-semibold">
                <button
                  type="button"
                  title="Rename session"
                  className="-mx-1.5 max-w-full truncate rounded-md px-1.5 transition-colors hover:bg-accent"
                  onClick={() => setRenaming({ id: activeId, place: "header" })}
                >
                  {title}
                </button>
              </h1>
            ) : (
              <h1 className="mt-0.5 truncate text-lg font-semibold">{title}</h1>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <StatusPill busy={pending} />
            {activeId && (
              <SessionActions
                label={title}
                busy={pending}
                className="border"
                onRename={() => setRenaming({ id: activeId, place: "header" })}
                onExport={(format) => exportSession(activeId, format)}
                onClear={() => clearSession(activeId)}
                onDelete={() => deleteSession(activeId)}
              />
            )}
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto" ref={scrollRef}>
          <section
            key={view}
            className="mx-auto w-full max-w-[900px] animate-in px-5 pt-8 pb-6 duration-300 fade-in md:px-7"
            aria-live="polite"
          >
            {messages.length === 0 && !pendingHere ? (
              <div className="flex min-h-[55vh] flex-col items-center justify-center text-center">
                <h2 className="mb-2 text-2xl font-semibold md:text-3xl">Ask your data a question.</h2>
                <p className="text-muted-foreground">Explore the ride-sharing database or run an ETL task.</p>
                <div className="mt-7 grid w-full max-w-2xl gap-2.5 sm:grid-cols-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <Button
                      key={suggestion}
                      variant="outline"
                      className="h-auto justify-start px-3.5 py-3 text-left font-normal whitespace-normal transition-all hover:-translate-y-px hover:border-primary/60"
                      disabled={pending}
                      onClick={() => send(suggestion)}
                    >
                      {suggestion}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <MessageView
                  key={message.id}
                  message={message}
                  onRevealDone={finishReveal}
                  onProgress={followReveal}
                />
              ))
            )}
            {pendingHere && <ThinkingIndicator />}
          </section>
        </div>

        {error && (
          <div
            role="alert"
            className="mx-auto flex w-full max-w-[900px] animate-in items-center justify-center gap-3 px-7 pt-2 text-sm text-destructive fade-in slide-in-from-bottom-1"
          >
            {error}
            <Button variant="link" size="xs" onClick={() => setError(null)}>
              Dismiss
            </Button>
          </div>
        )}
        <Composer value={draft} busy={pending} onChange={setDraft} onSubmit={() => send(draft)} />
      </main>

      <ConfirmDialog options={confirmOptions} open={confirmOpen} onResult={settleConfirm} />
    </div>
  );
}
