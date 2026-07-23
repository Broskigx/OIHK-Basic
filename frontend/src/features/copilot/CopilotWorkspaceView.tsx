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
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  createCopilotConversation,
  deleteCopilotConversation,
  getLocalModelConfiguration,
  listCopilotConversations,
  listCopilotMessages,
  sendCopilotMessage,
  updateCopilotConversation,
} from "../../api";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type { CopilotConversation, CopilotMessage, LocalModelConfiguration } from "../../types";

function timestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
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

  async function refreshConversations(preferredId = activeId) {
    const rows = await listCopilotConversations(caseId, includeArchived);
    setConversations(rows);
    const nextId = rows.some((row) => row.id === preferredId) ? preferredId : (rows[0]?.id ?? "");
    setActiveId(nextId);
    setMessages(nextId ? await listCopilotMessages(nextId) : []);
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      listCopilotConversations(caseId, includeArchived),
      getLocalModelConfiguration(),
    ])
      .then(async ([rows, modelConfiguration]) => {
        if (cancelled) return;
        setConversations(rows);
        setConfiguration(modelConfiguration);
        const nextId = rows[0]?.id ?? "";
        setActiveId(nextId);
        setMessages(nextId ? await listCopilotMessages(nextId) : []);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load local conversations");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [caseId, includeArchived]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const visibleConversations = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return conversations;
    return conversations.filter((item) => item.title.toLocaleLowerCase().includes(normalized));
  }, [conversations, query]);

  const active = conversations.find((item) => item.id === activeId);
  const modelReady = Boolean(configuration?.endpoint && configuration?.model);

  async function openConversation(conversationId: string) {
    setActiveId(conversationId);
    setLoading(true);
    setError("");
    try {
      setMessages(await listCopilotMessages(conversationId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open the conversation");
    } finally {
      setLoading(false);
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
        const created = await createCopilotConversation({ case_id: caseId, title: "New conversation" });
        conversationId = created.id;
        setActiveId(created.id);
        setConversations((current) => [created, ...current]);
      }
      const optimistic: CopilotMessage = {
        id: `pending-${Date.now()}`,
        conversation_id: conversationId,
        case_id: caseId,
        role: "user",
        content,
        provider: "local",
        tool_calls: [],
        created_at: new Date().toISOString(),
      };
      setMessages((current) => [...current, optimistic]);
      setDraft("");
      const controller = new AbortController();
      abortRef.current = controller;
      const reply = await sendCopilotMessage(conversationId, content, controller.signal);
      setMessages((current) => [
        ...current.filter((item) => item.id !== optimistic.id),
        reply.user_message,
        reply.assistant_message,
      ]);
      await refreshConversations(conversationId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The local model did not respond");
      if (conversationId) {
        setMessages(await listCopilotMessages(conversationId).catch(() => []));
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
    await updateCopilotConversation(active.id, { title });
    await refreshConversations(active.id);
  }

  async function toggleArchive() {
    if (!active) return;
    await updateCopilotConversation(active.id, { archived: !active.archived });
    await refreshConversations("");
  }

  async function removeActive() {
    if (!active || !window.confirm(`Delete “${active.title}” and all of its local messages?`)) return;
    await deleteCopilotConversation(active.id);
    await refreshConversations("");
  }

  return (
    <div className="platform-view copilot-workspace">
      <WorkspaceHeader
        eyebrow="Local Copilot"
        title="Copilot"
        description="Durable investigation conversations powered only by the local model endpoint you choose. Model output remains an unverified draft."
        actions={
          <button type="button" onClick={() => { setActiveId(""); setMessages([]); setError(""); }}>
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
          <label className="local-checkbox"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} /> Include archived</label>
          <div className="copilot-history-list">
            {visibleConversations.length === 0 ? (
              <p>No saved conversations.</p>
            ) : visibleConversations.map((item) => (
              <button type="button" key={item.id} className={item.id === activeId ? "active" : ""} onClick={() => void openConversation(item.id)}>
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
                <p>{message.content}</p>
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
