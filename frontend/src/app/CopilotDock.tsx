import { ArrowRight, Bot, ChevronLeft, ChevronRight, MessageSquareText, X } from "lucide-react";
import type { LocalModelRuntimeStatus } from "../types";
import type { PlatformArea } from "./navigation";

function suggestionFor(area: PlatformArea) {
  if (area === "dashboard") return { title: "Summarize activity", detail: "Review recorded local events and recent investigations." };
  if (area === "investigations") return { title: "Summarize case", detail: "Work from the active investigation context." };
  if (area === "graph") return { title: "Explain relationships", detail: "Reason over evidence-backed graph connections." };
  if (area === "evidence") return { title: "Analyze selection", detail: "Use the active investigation evidence context." };
  if (area === "reports") return { title: "Draft report outline", detail: "Prepare a structured local report workflow." };
  return { title: "Open Copilot", detail: "Continue in the private local conversation workspace." };
}

export function CopilotDock({
  area,
  open,
  collapsed,
  modelStatus,
  onOpen,
  onClose,
  onToggleCollapsed,
  onNavigate,
}: {
  area: PlatformArea;
  open: boolean;
  collapsed: boolean;
  modelStatus: LocalModelRuntimeStatus | null;
  onOpen: () => void;
  onClose: () => void;
  onToggleCollapsed: () => void;
  onNavigate: (area: PlatformArea) => void;
}) {
  const suggestion = suggestionFor(area);
  if (!open) {
    return <button type="button" className="copilot-launcher" onClick={onOpen} aria-label="Open Copilot"><Bot size={18} /></button>;
  }

  return (
    <aside className={collapsed ? "copilot-dock collapsed" : "copilot-dock"} aria-label="Local Copilot">
      <header>
        <div><Bot size={17} /><span>Copilot</span></div>
        <div>
          <button type="button" onClick={onToggleCollapsed} aria-label={collapsed ? "Expand Copilot" : "Collapse Copilot"} title={collapsed ? "Expand" : "Collapse"}>
            {collapsed ? <ChevronLeft size={15} /> : <ChevronRight size={15} />}
          </button>
          <button type="button" onClick={onClose} aria-label="Close Copilot" title="Close"><X size={15} /></button>
        </div>
      </header>
      {collapsed ? (
        <button type="button" className="copilot-collapsed-action" onClick={() => onNavigate("copilot")} title={suggestion.title}><MessageSquareText size={17} /></button>
      ) : (
        <div className="copilot-dock-body">
          <div className="copilot-identity">
            <span><Bot size={26} /></span>
            <strong>Local Copilot</strong>
            <small>{modelStatus?.connected ? `${modelStatus.model || "Model"} ready` : modelStatus?.configured ? "Model endpoint offline" : "No local model configured"}</small>
          </div>
          <button type="button" className="copilot-suggestion" onClick={() => onNavigate("copilot")}>
            <MessageSquareText size={16} />
            <span><strong>{suggestion.title}</strong><small>{suggestion.detail}</small></span>
            <ArrowRight size={14} />
          </button>
          <p>Copilot opens the existing case-scoped conversation workspace. It does not generate answers until you submit a request.</p>
        </div>
      )}
    </aside>
  );
}
