"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type ChatMessage, type SessionSummary } from "@/lib/api";
import { usePrefersReducedMotion } from "@/lib/hooks";
import Composer from "./Composer";
import MessageView, { type UiMessage } from "./MessageView";
import Sidebar from "./Sidebar";
import ThinkingIndicator from "./ThinkingIndicator";

const NEW_CHAT_TITLE = "New chat";
const SUGGESTIONS = [
  "What payment methods are available?",
  "Which 3 cities have the most users?",
  "What are the most common reasons rides get cancelled?",
  "Extract data from https://pokeapi.co/api/v2/pokemon and save it to data/extract as csv",
];

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
  const viewRef = useRef(0);
  const nextId = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const reduceMotion = usePrefersReducedMotion();

  const pending = pendingView !== null;
  const pendingHere = pendingView === view;

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
    setMessages((current) => [...current, userMessage]);

    try {
      let sessionId = activeId;
      if (!sessionId) {
        const created = await api.createSession(sessionTitle(message));
        sessionId = created.session_id;
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
      refreshSessions().catch(() => undefined);
    }
  }

  async function deleteSession(sessionId: string) {
    if (!window.confirm("Delete this session? This cannot be undone.")) return;
    try {
      await api.deleteSession(sessionId);
      if (sessionId === activeId) newChat();
      await refreshSessions();
    } catch (caught) {
      setError(errorText(caught));
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        disabled={pending}
        onNew={newChat}
        onSelect={openSession}
        onDelete={deleteSession}
      />

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-title">
            <div className="eyebrow">Unified data workspace</div>
            <h1>{title}</h1>
          </div>
          <div className={`status${pending ? " busy" : ""}`} role="status">
            {pending ? "Working" : "Ready"}
          </div>
        </header>

        <div className="chat-scroll" ref={scrollRef}>
          <section key={view} className="chat fade-in" aria-live="polite">
            {messages.length === 0 && !pendingHere ? (
              <div className="empty">
                <h2>Ask your data a question.</h2>
                <p>Explore the ride-sharing database or run an ETL task.</p>
                <div className="suggestions">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      className="suggestion"
                      disabled={pending}
                      onClick={() => send(suggestion)}
                    >
                      {suggestion}
                    </button>
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
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <Composer value={draft} busy={pending} onChange={setDraft} onSubmit={() => send(draft)} />
      </main>
    </div>
  );
}
