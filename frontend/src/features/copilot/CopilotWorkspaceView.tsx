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
  Trash2,
  Copy,
  RefreshCw,
  Eye,
  StopCircle,
  Globe,
  Cpu,
  Boxes,
  Database,
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
    // Storage unavailable
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
  const generationRef = useRef(0);
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  const intentNewRef = useRef(false);
  const storageKey = useMemo(() => sessionKey(caseId), [caseId]);

  const applyIfCurrent = useCallback((generation: number, fn: () => void) => {
    if (generation === generationRef.current) fn();
  }, []);

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
      const userInitiatedAbort =
        detail === "Operation cancelled"
        && (intentNewRef.current || !activeIdRef.current || activeIdRef.current !== conversationId);
      if (!userInitiatedAbort) setError(detail);
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
    if (!active || !window.confirm(`Delete "${active.title}" and all of its local messages?`)) return;
    try {
      await deleteCopilotConversation(active.id);
      clearSession(storageKey);
      await refreshConversations("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete the conversation");
    }
  }

  function startNewConversation() {
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

      <div className="platform-inline-status">
        <ShieldCheck size={16} />
        {modelReady
          ? `${configuration?.provider} · ${configuration?.model} · ${configuration?.endpoint}`
          : "No local model configured. The rest of OIHK Basic remains available."}
        {!modelReady && <button type="button" onClick={onOpenModels}><Settings2 size={13} /> Configure</button>}
      </div>
      {error && <div className="platform-inline-error" role="alert">{error}</div>}

      {/* ── 3-Column Layout ── */}
      <div className="copilot-layout">
        {/* Column 1: Conversations */}
        <aside className="copilot-sidebar">
          <label className="copilot-search">
            <Search size={13} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search conversations" />
          </label>
          <label className="copilot-checkbox">
            <input type="checkbox" checked={includeArchived} disabled={sending} onChange={(event) => setIncludeArchived(event.target.checked)} />
            Include archived
          </label>
          <div className="copilot-conversation-list">
            {visibleConversations.length === 0 ? (
              <p className="copilot-empty-text">No saved conversations.</p>
            ) : visibleConversations.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`copilot-conversation-item ${item.id === activeId ? "active" : ""}`}
                onClick={() => void openConversation(item.id)}
                disabled={sending}
              >
                <strong>{item.title}</strong>
                <span>{item.message_count} messages · {timestamp(item.updated_at)}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* Column 2: Chat */}
        <section className="copilot-chat">
          <header className="copilot-chat-header">
            <div className="copilot-chat-header-info">
              <Bot size={18} />
              <div>
                <strong>{active?.title ?? "New conversation"}</strong>
                <small>{caseId ? "Investigation-linked" : "General local chat"}</small>
              </div>
            </div>
            <div className="copilot-chat-actions">
              {active && (
                <>
                  <button type="button" onClick={() => void renameActive()} title="Rename"><Pencil size={13} /></button>
                  <button type="button" onClick={() => void toggleArchive()} title={active.archived ? "Restore" : "Archive"}>
                    {active.archived ? <RotateCcw size={13} /> : <Archive size={13} />}
                  </button>
                  <button type="button" onClick={() => void removeActive()} title="Delete"><Trash2 size={13} /></button>
                </>
              )}
            </div>
          </header>

          <div className="copilot-messages" ref={scrollRef}>
            {loading ? (
              <p className="copilot-loading">Loading local history...</p>
            ) : messages.length === 0 ? (
              <div className="copilot-empty">
                <Bot size={28} />
                <strong>Start with a question</strong>
                <p>No conversation is stored until you send the first message.</p>
              </div>
            ) : (
              messages.map((message) => {
                const isUser = message.role === "user";
                return (
                  <article key={message.id} className={`copilot-message ${isUser ? "user" : "assistant"}`}>
                    <div className="copilot-message-header">
                      <span className="copilot-message-role">{isUser ? "You" : message.provider}</span>
                      {!isUser && (
                        <span className="copilot-message-type">
                          {message.content.startsWith("I'll search") ? "Search Plan" : "Local Answer"}
                        </span>
                      )}
                    </div>
                    <p className="copilot-message-content">
                      {message.content || (message.id.startsWith("pending-assistant") ? "..." : "")}
                    </p>
                    <div className="copilot-message-footer">
                      <time>{timestamp(message.created_at)}</time>
                      {!isUser && message.content && !message.id.startsWith("pending") && (
                        <div className="copilot-message-actions">
                          <button type="button" title="Copy" onClick={() => navigator.clipboard.writeText(message.content)}>
                            <Copy size={10} />
                          </button>
                          <button type="button" title="Retry" onClick={() => {}}>
                            <RefreshCw size={10} />
                          </button>
                          <button type="button" title="View sources">
                            <Eye size={10} />
                          </button>
                        </div>
                      )}
                    </div>
                  </article>
                );
              })
            )}
            {sending && (
              <div className="copilot-generating">
                <Bot size={14} />
                Local model is generating...
              </div>
            )}
          </div>

          <form className="copilot-composer" onSubmit={submit}>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              rows={2}
              placeholder={modelReady ? "Ask the local model..." : "Configure LM Studio or Ollama to enable Copilot"}
              disabled={!modelReady || sending}
            />
            <div className="copilot-composer-actions">
              <span className="copilot-composer-hint">Local inference only. No cloud fallback.</span>
              <div className="copilot-composer-buttons">
                <span className="copilot-composer-status">
                  {modelReady ? "Connected" : "Disconnected"}
                </span>
                {sending ? (
                  <button type="button" onClick={() => abortRef.current?.abort()}>
                    <StopCircle size={13} /> Stop
                  </button>
                ) : (
                  <button type="submit" className="platform-primary-btn" disabled={!modelReady || !draft.trim()}>
                    <Send size={13} /> Send
                  </button>
                )}
              </div>
            </div>
          </form>
        </section>

        {/* Column 3: Context */}
        <aside className="copilot-context">
          <div className="copilot-context-section">
            <h4><Boxes size={13} /> Active Case</h4>
            <p className="copilot-context-value">{caseId ? `Investigation ${caseId.slice(0, 8)}` : "No active case"}</p>
          </div>

          <div className="copilot-context-section">
            <h4><Globe size={13} /> Sources</h4>
            <p className="copilot-context-value">No sources selected for this context.</p>
          </div>

          <div className="copilot-context-section">
            <h4><Cpu size={13} /> Tools</h4>
            <div className="copilot-context-tools">
              <span className={modelReady ? "available" : "unavailable"}>Local Model</span>
              <span className="available">DNS</span>
              <span className="available">RDAP</span>
              <span className="available">Certificate Search</span>
            </div>
          </div>

          <div className="copilot-context-section">
            <h4><Database size={13} /> Search Plan</h4>
            <p className="copilot-context-value">No active search plan.</p>
          </div>

          <div className="copilot-context-section">
            <h4><ShieldCheck size={13} /> Confirmation Status</h4>
            <p className="copilot-context-value">Output is unverified. Review before use.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}