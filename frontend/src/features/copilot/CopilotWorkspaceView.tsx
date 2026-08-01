import {
  Archive,
  Bot,
  MessageSquarePlus,
  Pencil,
  RotateCcw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Square,
  Trash2,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createCopilotConversation,
  deleteCopilotConversation,
  getLocalModelConfiguration,
  listCopilotConversations,
  listCopilotMessages,
  streamCopilotMessage,
  updateCopilotConversation,
} from "../../api";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type { CopilotConversation, CopilotMessage, LocalModelConfiguration } from "../../types";

function timestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

/** Session-scoped persistence key so switching views (or areas) restores the last conversation. */
function sessionKey(caseId: string | null): string {
  return `oihk.copilot.session.${caseId ?? "global"}`;
}

type SavedSession = { caseId: string | null; activeId: string; draft: string };

function readSession(key: string): SavedSession | null {
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as SavedSession) : null;
  } catch {
    return null;
  }
}

function writeSession(key: string, session: SavedSession): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(session));
  } catch {
    // Storage unavailable (private mode / quota) — the server is the source of truth.
  }
}

function clearSession(key: string): void {
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // ignore
  }
}

export function CopilotWorkspaceView({
  caseId,
  targetId,
  onOpenModels,
}: {
  caseId: string | null;
  targetId: string;
  onOpenModels: () => void;
}) {
  const [conversations, setConversations] = useState<CopilotConversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [configuration, setConfiguration] = useState<LocalModelConfiguration | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Guards against out-of-order async responses (the root cause of "empty chats"
  // and "unexpected new chats"). Every load increments the generation; only the
  // latest generation may commit state.
  const generationRef = useRef(0);
  // Mirrors the latest activeId so async callbacks can verify the conversation
  // the user is viewing without depending on stale closures.
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  // Explicit intent to start a fresh conversation (set by the "New conversation" button).
  const intentNewRef = useRef(false);

  const storageKey = useMemo(() => sessionKey(caseId), [caseId]);

  const applyIfCurrent = useCallback((generation: number, fn: () => void) => {
    if (generation === generationRef.current) fn();
  }, []);

  /** Reload the conversation list, keeping the current/preferred conversation when possible. */
  const refreshConversations = useCallback(
    async (preferredId = activeId) => {
      const generation = ++generationRef.current;
      try {
        const rows = await listCopilotConversations(caseId, includeArchived);
        if (generation !== generationRef.current) return;
        setConversations(rows);
        const candidate = preferredId || activeId;
        const nextId = rows.some((row) => row.id === candidate) ? candidate : (rows[0]?.id ?? "");
        setActiveId(nextId);
        if (nextId) writeSession(storageKey, { caseId, activeId: nextId, draft });
        const history = nextId ? await listCopilotMessages(nextId) : [];
        if (generation === generationRef.current) setMessages(history);
      } catch (cause) {
        applyIfCurrent(generation, () => {
          setError(cause instanceof Error ? cause.message : "Could not load local conversations");
        });
      }
    },
    [activeId, applyIfCurrent, caseId, draft, includeArchived, storageKey],
  );

  // Initial load + restore the session the user was working on before switching views.
  useEffect(() => {
    let cancelled = false;
    const generation = ++generationRef.current;
    setLoading(true);
    setError("");
    const saved = readSession(storageKey);
    Promise.all([listCopilotConversations(caseId, includeArchived), getLocalModelConfiguration()])
      .then(async ([rows, modelConfiguration]) => {
        if (cancelled || generation !== generationRef.current) return;
        setConversations(rows);
        setConfiguration(modelConfiguration);
        const restored =
          saved && saved.caseId === caseId && rows.some((row) => row.id === saved.activeId)
            ? saved.activeId
            : (rows[0]?.id ?? "");
        setActiveId(restored);
        setMessages(restored ? await listCopilotMessages(restored) : []);
        if (saved && saved.caseId === caseId && saved.draft) setDraft(saved.draft);
      })
      .catch((cause) => {
        if (!cancelled && generation === generationRef.current) {
          setError(cause instanceof Error ? cause.message : "Could not load local conversations");
        }
      })
      .finally(() => {
        if (!cancelled && generation === generationRef.current) setLoading(false);
      });
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [caseId, includeArchived, storageKey]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  // Persist the active conversation + draft across view switches.
  useEffect(() => {
    if (!loading) writeSession(storageKey, { caseId, activeId, draft });
  }, [activeId, caseId, draft, loading, storageKey]);

  const visibleConversations = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return conversations;
    return conversations.filter((item) => item.title.toLocaleLowerCase().includes(normalized));
  }, [conversations, query]);

  const active = conversations.find((item) => item.id === activeId);
  const modelReady = Boolean(configuration?.endpoint && configuration?.model);

  async function openConversation(conversationId: string) {
    // If a generation is in flight for another conversation, cancel it so its
    // reply can never be applied to the newly selected conversation.
    abortRef.current?.abort();
    const generation = ++generationRef.current;
    intentNewRef.current = false;
    setActiveId(conversationId);
    setLoading(true);
    setError("");
    try {
      const history = await listCopilotMessages(conversationId);
      applyIfCurrent(generation, () => setMessages(history));
    } catch (cause) {
      applyIfCurrent(generation, () => {
        setError(cause instanceof Error ? cause.message : "Could not open the conversation");
      });
    } finally {
      applyIfCurrent(generation, () => setLoading(false));
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || sending || !modelReady) return;
    setError("");
    setSending(true);
    let conversationId = activeId;
    try {
      if (!conversationId) {
        // Never create a conversation silently while an active session exists.
        // Only create when the user explicitly chose "New conversation" or when
        // there are no conversations at all.
        if (!intentNewRef.current && conversations.length > 0) {
          conversationId = conversations[0].id;
          setActiveId(conversationId);
        } else {
          const created = await createCopilotConversation({
            case_id: caseId,
            title: "New conversation",
            model: configuration?.model ?? "",
          });
          conversationId = created.id;
          intentNewRef.current = false;
          setActiveId(created.id);
          setConversations((current) => [created, ...current]);
          writeSession(storageKey, { caseId, activeId: created.id, draft: "" });
        }
      }

      const userPendingId = `pending-user-${Date.now()}`;
      const assistantPendingId = `pending-assistant-${Date.now()}`;
      setMessages((current) => [
        ...current,
        {
          id: userPendingId,
          conversation_id: conversationId,
          case_id: caseId,
          role: "user",
          content,
          provider: "local",
          tool_calls: [],
          created_at: new Date().toISOString(),
        },
        {
          id: assistantPendingId,
          conversation_id: conversationId,
          case_id: caseId,
          role: "assistant",
          content: "",
          provider: configuration?.provider ?? "local",
          tool_calls: [],
          created_at: new Date().toISOString(),
        },
      ]);
      setDraft("");
      const controller = new AbortController();
      abortRef.current = controller;

      const reply = await streamCopilotMessage(conversationId, content, controller.signal, (delta) => {
        setMessages((current) =>
          current.map((item) =>
            item.id === assistantPendingId ? { ...item, content: item.content + delta } : item,
          ),
        );
      });
      // Only commit the reply to the UI if the user is still viewing this
      // conversation. If they switched away (allowed during streaming), the
      // messages they switched to are already loaded — do not overwrite them.
      if (activeIdRef.current && activeIdRef.current !== conversationId) {
        const targetHistory = await listCopilotMessages(activeIdRef.current).catch(() => null);
        if (targetHistory) setMessages(targetHistory);
      } else if (activeIdRef.current === conversationId) {
        setMessages((current) => [
          ...current.filter((item) => item.id !== userPendingId && item.id !== assistantPendingId),
          reply.user_message,
          reply.assistant_message,
        ]);
        await refreshConversations(conversationId);
      }
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "The local model did not respond";
      // Suppress the error banner when the abort was intentional (the user
      // switched away or started a new conversation), so it never leaks into
      // the new context.
      const userInitiatedAbort =
        detail === "Operation cancelled"
        && (intentNewRef.current || !activeIdRef.current || activeIdRef.current !== conversationId);
      if (!userInitiatedAbort) setError(detail);
      // Reload the persisted state for the conversation the user is actually
      // viewing. If they switched away (which aborts the in-flight request),
      // the target conversation already shows its own history — do nothing.
      if (conversationId && activeIdRef.current === conversationId) {
        const history = await listCopilotMessages(conversationId).catch(() => null);
        if (history) setMessages(history);
      }
    } finally {
      abortRef.current = null;
      setSending(false);
    }
  }

  async function renameActive() {
    if (!active) return;
    const title = window.prompt("Conversation name", active.title)?.trim();
    if (!title || title === active.title) return;
    try {
      await updateCopilotConversation(active.id, { title });
      await refreshConversations(active.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not rename the conversation");
    }
  }

  async function toggleArchive() {
    if (!active) return;
    try {
      await updateCopilotConversation(active.id, { archived: !active.archived });
      await refreshConversations("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update the conversation");
    }
  }

  async function removeActive() {
    if (!active || !window.confirm(`Delete “${active.title}” and all of its local messages?`)) return;
    try {
      await deleteCopilotConversation(active.id);
      clearSession(storageKey);
      await refreshConversations("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete the conversation");
    }
  }

  function startNewConversation() {
    // Stop any in-flight generation before switching to the fresh session.
    abortRef.current?.abort();
    const generation = ++generationRef.current;
    intentNewRef.current = true;
    setActiveId("");
    setMessages([]);
    setDraft("");
    setError("");
    applyIfCurrent(generation, () => setLoading(false));
  }

  return (
    <div className="platform-view copilot-workspace">
      <WorkspaceHeader
        eyebrow="Local Copilot"
        title="Copilot"
        description="Durable investigation conversations powered only by the local model endpoint you choose. Model output remains an unverified draft."
        actions={
          <button type="button" onClick={startNewConversation} disabled={sending}>
            <MessageSquarePlus size={14} /> New conversation
          </button>
        }
      />

      <div className="local-privacy-note">
        <ShieldCheck size={16} />
        {modelReady
          ? `${configuration?.provider} · ${configuration?.model} · ${configuration?.endpoint}`
          : "No local model configured. The rest of OIHK Basic remains available."}
        {!modelReady && <button type="button" onClick={onOpenModels}><Settings2 size={13} /> Configure</button>}
      </div>
      {targetId && <div className="platform-context-note">Selected target context: {targetId}</div>}
      {error && <div className="platform-inline-error" role="alert">{error}</div>}

      <div className="copilot-layout">
        <aside className="copilot-history">
          <label className="copilot-search"><Search size={13} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search conversations" /></label>
          <label className="local-checkbox"><input type="checkbox" checked={includeArchived} disabled={sending} onChange={(event) => setIncludeArchived(event.target.checked)} /> Include archived</label>
          <div className="copilot-history-list">
            {visibleConversations.length === 0 ? (
              <p>No saved conversations.</p>
            ) : visibleConversations.map((item) => (
              <button type="button" key={item.id} className={item.id === activeId ? "active" : ""} onClick={() => void openConversation(item.id)} disabled={sending}>
                <strong>{item.title}</strong><span>{item.message_count} messages · {timestamp(item.updated_at)}</span>
              </button>
            ))}
          </div>
        </aside>

        <section className="copilot-conversation">
          <header>
            <div><Bot size={18} /><span><strong>{active?.title ?? "New conversation"}</strong><small>{caseId ? "Investigation-linked" : "General local chat"}</small></span></div>
            {active && <div className="copilot-conversation-actions">
              <button type="button" onClick={() => void renameActive()} title="Rename"><Pencil size={13} /></button>
              <button type="button" onClick={() => void toggleArchive()} title={active.archived ? "Restore" : "Archive"}>{active.archived ? <RotateCcw size={13} /> : <Archive size={13} />}</button>
              <button type="button" onClick={() => void removeActive()} title="Delete"><Trash2 size={13} /></button>
            </div>}
          </header>
          <div className="copilot-messages" ref={scrollRef}>
            {loading ? <p>Loading local history…</p> : messages.length === 0 ? (
              <div className="copilot-empty"><Bot size={28} /><strong>Start with a question</strong><p>No conversation is stored until you send the first message.</p></div>
            ) : messages.map((message) => (
              <article key={message.id} className={message.role}>
                <span>{message.role === "user" ? "You" : message.provider}</span>
                <p>{message.content || (message.id.startsWith("pending-assistant") ? "…" : "")}</p>
                <time>{timestamp(message.created_at)}</time>
              </article>
            ))}
            {sending && <div className="copilot-generating">Local model is generating…</div>}
          </div>
          <form className="copilot-composer" onSubmit={submit}>
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} rows={3} placeholder={modelReady ? "Ask the local model…" : "Configure LM Studio or Ollama to enable Copilot"} disabled={!modelReady || sending} />
            {sending ? (
              <button type="button" onClick={() => abortRef.current?.abort()}><Square size={13} /> Cancel</button>
            ) : (
              <button type="submit" className="platform-primary-btn" disabled={!modelReady || !draft.trim()}><Send size={13} /> Send</button>
            )}
          </form>
        </section>
      </div>
    </div>
  );
}
