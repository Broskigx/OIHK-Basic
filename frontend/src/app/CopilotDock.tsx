import { Bot, ChevronLeft, ChevronRight, MessageSquareText, X } from "lucide-react";
import { CopilotAgentPanel } from "../features/copilot/CopilotWorkspaceView";
import type { LocalModelRuntimeStatus } from "../types";

export function CopilotDock({
  open,
  collapsed,
  caseId,
  modelStatus,
  onOpen,
  onClose,
  onToggleCollapsed,
  onOpenModels,
  onDataChanged,
}: {
  open: boolean;
  collapsed: boolean;
  caseId: string | null;
  modelStatus: LocalModelRuntimeStatus | null;
  onOpen: () => void;
  onClose: () => void;
  onToggleCollapsed: () => void;
  onOpenModels: () => void;
  onDataChanged: () => void;
}) {
  if (!open) {
    return <button type="button" className="copilot-launcher" onClick={onOpen} aria-label="Open OIHK Agent"><Bot size={18} /></button>;
  }

  const modelLabel = modelStatus?.connected
    ? `${modelStatus.model || "Local model"} ready`
    : modelStatus?.configured
      ? "Model endpoint offline"
      : "Model setup required";

  return (
    <aside className={collapsed ? "copilot-dock collapsed" : "copilot-dock"} aria-label="OIHK Agent">
      <header>
        <div className="copilot-dock-title">
          <span className={modelStatus?.connected ? "connected" : "offline"}><Bot size={17} /></span>
          <span><strong>OIHK Agent</strong><small>{modelLabel}</small></span>
        </div>
        <div>
          <button type="button" onClick={onToggleCollapsed} aria-label={collapsed ? "Expand OIHK Agent" : "Collapse OIHK Agent"} title={collapsed ? "Expand" : "Collapse"}>
            {collapsed ? <ChevronLeft size={15} /> : <ChevronRight size={15} />}
          </button>
          <button type="button" onClick={onClose} aria-label="Close OIHK Agent" title="Close"><X size={15} /></button>
        </div>
      </header>
      {collapsed ? (
        <button type="button" className="copilot-collapsed-action" onClick={onToggleCollapsed} title="Expand OIHK Agent"><MessageSquareText size={17} /></button>
      ) : (
        <CopilotAgentPanel caseId={caseId} modelStatus={modelStatus} onOpenModels={onOpenModels} onDataChanged={onDataChanged} />
      )}
    </aside>
  );
}
