import { GitBranch, Network, Plus, Share2 } from "lucide-react";
import { GRAPH_VIEW_OPTIONS, type GraphViewMode } from "./graphModes";

const MODE_ICONS = {
  network: Network,
  hierarchy: GitBranch,
  connections: Share2,
};

export function GraphModeTabs({
  value,
  onChange,
  compact = false,
}: {
  value: GraphViewMode;
  onChange: (mode: GraphViewMode) => void;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "graph-view-tabs compact" : "graph-view-tabs"} role="tablist" aria-label="Vistas del grafo">
      {GRAPH_VIEW_OPTIONS.map((option) => {
        const Icon = MODE_ICONS[option.id];
        const selected = option.id === value;
        return (
          <button
            key={option.id}
            type="button"
            role="tab"
            aria-selected={selected}
            className={selected ? "selected" : ""}
            onClick={() => onChange(option.id)}
          >
            <Icon size={16} />
            <span>
              <strong>{option.label}</strong>
              {!compact && <small>{option.description}</small>}
            </span>
          </button>
        );
      })}
      <span className="graph-view-tabs-future" title="La barra admite nuevas vistas sin reorganizar el workspace">
        <Plus size={14} />
        Más vistas
      </span>
    </div>
  );
}
