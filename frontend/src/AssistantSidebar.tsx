import {
  AlertTriangle,
  BrainCircuit,
  Loader2,
  Network,
  Paperclip,
  Search,
  Send,
  Sparkles,
  Star,
  Wand2,
  Wrench,
  X,
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

import { assistantChat, investigateStream } from "./api";
import type { InvestigateEvent, ToolCall } from "./types";

type ChatTurn = {
  role: "user" | "assistant";
  content: string;
  provider?: string;
  toolCalls?: ToolCall[];
  events?: InvestigateEvent[];
  streaming?: boolean;
  attachmentUrl?: string;
  attachmentName?: string;
};

const SUGGESTIONS = [
  "Investiga a Ada Lovelace",
  "Investiga a Grace Hopper y añade a su equipo al grafo",
  "whois github.com",
  "geolocaliza 8.8.8.8",
  "Analiza el adjunto forense",
  "Resume el caso",
];

function EventLine({ event }: { event: InvestigateEvent }) {
  switch (event.type) {
    case "status":
      return (
        <div className="inv-line inv-status">
          <Search size={12} />
          <span>{event.text}</span>
        </div>
      );
    case "thought":
      return (
        <div className="inv-line inv-thought">
          <BrainCircuit size={12} />
          <span>{event.text}</span>
        </div>
      );
    case "tool":
      return (
        <div className={`inv-line inv-tool${event.status === "done" && event.ok === false ? " failed" : ""}`}>
          {event.status === "running" ? <Loader2 size={12} className="ip-spin" /> : <Wrench size={12} />}
          <span>
            <b>{event.tool}</b>
            {event.status === "done" && event.summary ? ` — ${event.summary}` : event.status === "running" ? "…" : ""}
          </span>
        </div>
      );
    case "finding":
      return (
        <div className="inv-line inv-finding">
          <Star size={12} />
          <span>{event.text}</span>
        </div>
      );
    case "graph":
      return (
        <div className="inv-line inv-graph">
          <Network size={12} />
          <span>
            Al grafo: <b>{event.label}</b>
            {event.relation ? ` — ${event.relation.replace(/_/g, " ")}` : ""}
            {event.description ? <em> · {event.description}</em> : null}
          </span>
        </div>
      );
    case "error":
      return (
        <div className="inv-line inv-error">
          <AlertTriangle size={12} />
          <span>{event.message}</span>
        </div>
      );
    default:
      return null;
  }
}

export function AssistantSidebar({
  caseId,
  targetId,
  onDataChanged,
}: {
  caseId: string | null;
  targetId: string | null;
  onDataChanged: (caseId: string | null) => void;
}) {
  const [turns, setTurns] = useState<ChatTurn[]>([
    {
      role: "assistant",
      content:
        "Hola, soy el investigador OSINT de OIHK. Puedo explorar la web, leer páginas y, cuando encuentro algo relevante, subirlo al grafo con su descripción — narrando cada paso aquí. También analizo imágenes con el motor forense y recuerdo lo aprendido. ¿A quién investigamos?",
      provider: "oihk",
    },
  ]);
  const [input, setInput] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, sending]);

  function patchLast(update: (turn: ChatTurn) => ChatTurn) {
    setTurns((prev) => {
      const next = [...prev];
      next[next.length - 1] = update(next[next.length - 1]);
      return next;
    });
  }

  async function runForensic(text: string, file: File) {
    const response = await assistantChat({
      message: text || "Analiza el archivo adjunto como evidencia forense.",
      case_id: caseId,
      target_id: targetId,
      file,
    });
    setTurns((prev) => [
      ...prev,
      { role: "assistant", content: response.reply, provider: response.provider, toolCalls: response.tool_calls },
    ]);
    if (response.data_changed) onDataChanged(response.case_id);
  }

  async function runInvestigation(text: string) {
    setTurns((prev) => [...prev, { role: "assistant", content: "", events: [], streaming: true, provider: "agente" }]);
    let refreshed = false;
    await investigateStream({ message: text, case_id: caseId, target_id: targetId }, (event) => {
      if (event.type === "final") {
        patchLast((turn) => ({ ...turn, content: event.reply, provider: event.provider ?? "agente", streaming: false }));
        if (event.data_changed) onDataChanged(event.case_id ?? caseId);
        return;
      }
      patchLast((turn) => ({ ...turn, events: [...(turn.events ?? []), event] }));
      if (event.type === "graph") {
        // Refresh the graph live as nodes are promoted.
        onDataChanged(event.case_id ?? caseId);
        refreshed = true;
      }
    });
    if (!refreshed) onDataChanged(caseId);
  }

  async function send(message: string, file: File | null = attachment) {
    const text = message.trim();
    if ((!text && !file) || sending) return;
    if (file && !caseId) {
      setError("Abre o crea un caso antes de adjuntar evidencia forense.");
      return;
    }
    setError("");
    setSending(true);
    const userContent = file ? `${text || "Analiza el archivo adjunto como evidencia forense."}` : text;
    const imgUrl = file?.type?.startsWith("image/") ? URL.createObjectURL(file) : undefined;
    setTurns((prev) => [...prev, { role: "user", content: userContent, attachmentUrl: imgUrl, attachmentName: file?.name }]);
    setInput("");
    setAttachment(null);
    try {
      if (file) {
        await runForensic(text, file);
      } else {
        await runInvestigation(text);
      }
    } catch (err) {
      const detail = err instanceof Error ? err.message : "El asistente no respondió";
      setError(detail);
      patchLast((turn) =>
        turn.role === "assistant" && turn.streaming
          ? { ...turn, content: `⚠️ ${detail}`, provider: "error", streaming: false }
          : turn,
      );
      setTurns((prev) =>
        prev[prev.length - 1]?.provider === "error"
          ? prev
          : [...prev, { role: "assistant", content: `⚠️ ${detail}`, provider: "error" }],
      );
    } finally {
      setSending(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    setAttachment(event.target.files?.[0] ?? null);
  }

  return (
    <aside className="assistant" aria-label="Copiloto OIHK">
      <header className="assistant-head">
        <div className="assistant-title">
          <BrainCircuit size={18} />
          <div>
            <strong>Investigador OIHK</strong>
            <span>explora, razona y construye el grafo</span>
          </div>
        </div>
        <span className="assistant-badge">
          <Wand2 size={12} /> agente
        </span>
      </header>

      <div className="assistant-log" ref={scrollRef}>
        {turns.map((turn, index) => (
          <div key={index} className={`chat-turn ${turn.role}`}>
            {turn.events && turn.events.length > 0 && (
              <div className="inv-feed">
                {turn.events.map((event, ei) => (
                  <EventLine key={ei} event={event} />
                ))}
              </div>
            )}
            {turn.attachmentUrl && (
              <div className="chat-attachment">
                <img src={turn.attachmentUrl} alt={turn.attachmentName ?? ""} />
              </div>
            )}
            {turn.content && <div className="chat-bubble">{turn.content}</div>}
            {turn.toolCalls && turn.toolCalls.length > 0 && (
              <div className="tool-chips">
                {turn.toolCalls.map((call, ti) => (
                  <span key={ti} className={call.ok ? "tool-chip" : "tool-chip failed"} title={call.result_summary}>
                    <Wrench size={11} /> {call.tool}
                  </span>
                ))}
              </div>
            )}
            {turn.streaming && (
              <div className="chat-bubble typing">
                <Loader2 size={13} className="ip-spin" /> investigando…
              </div>
            )}
            {turn.provider && turn.role === "assistant" && turn.provider !== "oihk" && turn.provider !== "agente" && (
              <small className="chat-provider">{turn.provider}</small>
            )}
          </div>
        ))}
        {sending && turns[turns.length - 1]?.role === "user" && (
          <div className="chat-turn assistant">
            <div className="chat-bubble typing">
              <Loader2 size={13} className="ip-spin" /> preparando…
            </div>
          </div>
        )}
      </div>

      <div className="assistant-suggestions">
        {SUGGESTIONS.map((suggestion) => (
          <button key={suggestion} type="button" onClick={() => void send(suggestion, null)} disabled={sending}>
            <Sparkles size={11} /> {suggestion}
          </button>
        ))}
      </div>

      {error && <div className="assistant-error">{error}</div>}
      {attachment && (
        <div className="assistant-attachment">
          <Paperclip size={13} />
          <span>{attachment.name}</span>
          <button type="button" onClick={() => setAttachment(null)} aria-label="Quitar adjunto" disabled={sending}>
            <X size={12} />
          </button>
        </div>
      )}

      <form className="assistant-input" onSubmit={onSubmit}>
        <button
          type="button"
          className="assistant-attach"
          onClick={() => fileRef.current?.click()}
          disabled={sending || !caseId}
          title={caseId ? "Adjuntar evidencia forense" : "Crea o abre un caso para adjuntar evidencia"}
          aria-label="Adjuntar evidencia"
        >
          <Paperclip size={16} />
        </button>
        <input ref={fileRef} type="file" hidden onChange={onFile} disabled={sending || !caseId} />
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void send(input);
            }
          }}
          placeholder="Pide una investigación o una acción… (Enter para enviar)"
          rows={2}
          disabled={sending}
        />
        <button type="submit" disabled={sending || (!input.trim() && !attachment)} aria-label="Enviar">
          <Send size={16} />
        </button>
      </form>
    </aside>
  );
}
