import { Camera, ChevronDown, ChevronUp, Download, Focus, Globe, Layers, Link2, Loader2, Maximize2, Minus, Network, Pencil, Pin, PinOff, Play, Plus, Redo2, Save, Search, Table2, Trash2, Undo2, Upload, Wand2, X, Zap } from "lucide-react";
import { ChangeEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { createGraphSnapshot, createMachine, deleteGraphEntity, deleteGraphRelationship, deleteGraphSnapshot, fetchGraphExport, getGraphWorkspace, listGraphSnapshots, listMachines, listTransforms, restoreGraphSnapshot, saveGraphWorkspace, updateGraphRelationship } from "../api";
import { GraphModeTabs } from "../features/graph/GraphModeTabs";
import { GRAPH_VIEW_OPTIONS, type GraphViewMode } from "../features/graph/graphModes";
import type { GraphAnalytics, GraphNode, GraphRead, GraphSnapshot, GraphWorkspace, MachineSpec, TransformSpec } from "../types";
import { score } from "../utils";
import { searchGraphNodes } from "../features/graph/graphSearch";
import { filterGraphForView, type GraphSourceFilter } from "../features/graph/graphFilters";
import { resolveGraphShortcut } from "../features/graph/graphKeyboard";
import { GraphView, type GraphViewHandle } from "./GraphView";
import { getNodeConfig } from "./graphTypes";

const ENRICHABLE = new Set(["domain", "host", "ip", "email"]);

type Popover = { node: GraphNode; left: number; top: number };
type ContextMenu = { node: GraphNode; left: number; top: number };

export function GraphPanel({
  graph,
  zoom,
  layoutVersion,
  showFilters,
  selectedNode,
  graphAnalytics,
  expanding,
  caseId,
  onSelectNode,
  onOpenNode,
  onExpandNode,
  onEnrichNode,
  onConnectNode,
  onRunTransform,
  onRunAdhocMachine,
  onRunSavedMachine,
  onImportCsv,
  onGraphChanged,
  onError,
}: {
  graph: GraphRead;
  zoom: number;
  layoutVersion: number;
  showFilters: boolean;
  selectedNode: GraphNode | null;
  graphAnalytics: GraphAnalytics | null;
  expanding: boolean;
  caseId: string;
  onSelectNode: (node: GraphNode | null) => void;
  onOpenNode: (node: GraphNode) => void;
  onExpandNode: (node: GraphNode) => void;
  onEnrichNode: (node: GraphNode) => void;
  onConnectNode: (node: GraphNode) => void;
  onRunTransform: (transformId: string, node: GraphNode) => void;
  onRunAdhocMachine: (transformIds: string[], node: GraphNode) => void;
  onRunSavedMachine: (machineId: string, node: GraphNode) => void;
  onImportCsv: (csv: string) => void;
  onGraphChanged: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [graphMode, setGraphMode] = useState<"graph" | "table">("graph");
  const [graphView, setGraphView] = useState<GraphViewMode>("network");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState<GraphSourceFilter>("all");
  const [popover, setPopover] = useState<Popover | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
  const [menuTransforms, setMenuTransforms] = useState<TransformSpec[]>([]);
  const [menuMachines, setMenuMachines] = useState<MachineSpec[]>([]);
  const [menuLoading, setMenuLoading] = useState(false);
  const [dataMenu, setDataMenu] = useState(false);
  const [workspace, setWorkspace] = useState<GraphWorkspace | null>(null);
  const [snapshots, setSnapshots] = useState<GraphSnapshot[]>([]);
  const [showSnapshots, setShowSnapshots] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchCursor, setSearchCursor] = useState(0);
  const [pinVersion, setPinVersion] = useState(0);
  const stageRef = useRef<HTMLDivElement>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);
  const graphViewRef = useRef<GraphViewHandle>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const saveWorkspaceTimer = useRef<number | null>(null);
  const workspaceLoadedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    workspaceLoadedRef.current = false;
    setWorkspace(null);
    setSnapshots([]);
    Promise.all([getGraphWorkspace(caseId), listGraphSnapshots(caseId)])
      .then(([saved, savedSnapshots]) => {
        if (cancelled) return;
        if (saveWorkspaceTimer.current !== null) window.clearTimeout(saveWorkspaceTimer.current);
        workspaceLoadedRef.current = true;
        setWorkspace(saved);
        setSnapshots(savedSnapshots);
        setGraphView(saved.view_mode);
        setTypeFilter(saved.filters.type ?? "all");
        setSourceFilter(saved.filters.source === "with-sources" || saved.filters.source === "without-sources" ? saved.filters.source : "all");
      })
      .catch((cause) => { if (!cancelled) onError(cause instanceof Error ? cause.message : "Could not load the saved graph workspace"); });
    return () => {
      cancelled = true;
      if (saveWorkspaceTimer.current !== null) window.clearTimeout(saveWorkspaceTimer.current);
    };
  }, [caseId, onError]);

  useEffect(() => {
    if (!workspaceLoadedRef.current) return;
    const current = graphViewRef.current?.getWorkspace();
    if (!current) return;
    const next = { ...current, view_mode: graphView, filters: { type: typeFilter, source: sourceFilter } };
    setWorkspace(next);
    if (saveWorkspaceTimer.current !== null) window.clearTimeout(saveWorkspaceTimer.current);
    saveWorkspaceTimer.current = window.setTimeout(() => {
      void saveGraphWorkspace(caseId, next).catch((cause) => onError(cause instanceof Error ? cause.message : "Could not save graph filters"));
    }, 500);
  }, [caseId, graphView, onError, sourceFilter, typeFilter]);

  function persistWorkspace(state: { positions: GraphWorkspace["positions"]; camera: GraphWorkspace["camera"] }) {
    const next: GraphWorkspace = {
      positions: state.positions,
      camera: state.camera,
      view_mode: graphView,
      filters: { type: typeFilter, source: sourceFilter },
    };
    setWorkspace(next);
    if (saveWorkspaceTimer.current !== null) window.clearTimeout(saveWorkspaceTimer.current);
    saveWorkspaceTimer.current = window.setTimeout(() => {
      void saveGraphWorkspace(caseId, next).catch((cause) => onError(cause instanceof Error ? cause.message : "Could not save graph positions"));
    }, 500);
  }

  async function createSnapshot() {
    const name = window.prompt("Snapshot name", `Graph ${new Date().toLocaleString()}`)?.trim();
    if (!name) return;
    const current = graphViewRef.current?.getWorkspace();
    if (current) await saveGraphWorkspace(caseId, { ...current, view_mode: graphView, filters: { type: typeFilter, source: sourceFilter } });
    const snapshot = await createGraphSnapshot(caseId, name);
    setSnapshots((items) => [snapshot, ...items]);
    setShowSnapshots(true);
  }

  async function restoreSnapshot(snapshot: GraphSnapshot) {
    const saved = await restoreGraphSnapshot(caseId, snapshot.id);
    setWorkspace(saved);
    setGraphView(saved.view_mode);
    setTypeFilter(saved.filters.type ?? "all");
    setSourceFilter(saved.filters.source === "with-sources" || saved.filters.source === "without-sources" ? saved.filters.source : "all");
    graphViewRef.current?.applyWorkspace({ positions: saved.positions, camera: saved.camera });
  }

  async function removeSnapshot(snapshot: GraphSnapshot) {
    if (!window.confirm(`Delete layout snapshot “${snapshot.name}”?`)) return;
    await deleteGraphSnapshot(caseId, snapshot.id);
    setSnapshots((items) => items.filter((item) => item.id !== snapshot.id));
  }

  async function editRelationship(edge: GraphRead["edges"][number]) {
    const label = window.prompt("Relationship label", edge.label)?.trim();
    if (!label) return;
    try {
      await updateGraphRelationship(edge.id, { label });
      await onGraphChanged();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not update relationship");
    }
  }

  async function removeRelationship(edge: GraphRead["edges"][number]) {
    if (!window.confirm(`Delete relationship “${edge.label}”?`)) return;
    try {
      await deleteGraphRelationship(edge.id);
      await onGraphChanged();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not delete relationship");
    }
  }

  function saveBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function downloadExport(kind: "graphml" | "csv-nodes" | "csv-edges") {
    setDataMenu(false);
    if (!caseId) return;
    try {
      const blob = await fetchGraphExport(caseId, kind);
      const ext = kind === "graphml" ? "graphml" : "csv";
      saveBlob(blob, `oihk-${kind}.${ext}`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "The graph could not be exported.");
    }
  }

  function exportPng() {
    setDataMenu(false);
    const canvases = Array.from(stageRef.current?.querySelectorAll("canvas") ?? []);
    const firstCanvas = canvases[0];
    if (!firstCanvas) {
      onError("There is no visible graph to export.");
      return;
    }
    try {
      const output = document.createElement("canvas");
      output.width = firstCanvas.width;
      output.height = firstCanvas.height;
      const context = output.getContext("2d");
      if (!context) throw new Error("The browser could not create the graph image.");
      context.fillStyle = "#07111f";
      context.fillRect(0, 0, output.width, output.height);
      canvases.forEach((canvas) => context.drawImage(canvas, 0, 0, output.width, output.height));
      output.toBlob((blob) => {
        if (blob) saveBlob(blob, "oihk-graph.png");
        else onError("The graph could not be encoded as PNG.");
      }, "image/png");
    } catch (err) {
      onError(err instanceof Error ? err.message : "The graph PNG could not be exported.");
    }
  }

  function onCsvFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onImportCsv(String(reader.result || ""));
    reader.onerror = () => onError("The CSV file could not be read.");
    reader.readAsText(file);
  }

  const graphTypes = useMemo(() => {
    const discovered = Array.from(new Set(graph.nodes.map((node) => node.type))).sort();
    return ["all", ...discovered.filter(Boolean)];
  }, [graph.nodes]);
  const sourceFilteredGraph = useMemo(
    () => filterGraphForView(graph, "all", sourceFilter),
    [graph, sourceFilter],
  );
  const filteredGraph = useMemo(
    () => filterGraphForView(graph, typeFilter, sourceFilter),
    [graph, sourceFilter, typeFilter],
  );
  const degree = useMemo(() => {
    const map = new Map<string, number>();
    graph.edges.forEach((edge) => {
      map.set(edge.source, (map.get(edge.source) ?? 0) + 1);
      map.set(edge.target, (map.get(edge.target) ?? 0) + 1);
    });
    return map;
  }, [graph.edges]);
  const topHubs = graphAnalytics?.top_hubs.slice(0, 4) ?? [];
  const activeGraphView = GRAPH_VIEW_OPTIONS.find((option) => option.id === graphView) ?? GRAPH_VIEW_OPTIONS[0];
  const searchResults = useMemo(() => {
    return searchGraphNodes(filteredGraph.nodes, searchQuery).slice(0, 50);
  }, [filteredGraph.nodes, searchQuery]);
  const engineWorkspace = useMemo(() => workspace ? { positions: workspace.positions, camera: workspace.camera } : null, [workspace]);
  void pinVersion;

  useEffect(() => setSearchCursor(0), [searchQuery]);

  // Close overlays if their node vanished (e.g. after a refresh/merge).
  useEffect(() => {
    if (popover && !graph.nodes.some((node) => node.id === popover.node.id)) setPopover(null);
    if (contextMenu && !graph.nodes.some((node) => node.id === contextMenu.node.id)) setContextMenu(null);
  }, [graph.nodes, popover, contextMenu]);

  function stageXY(screen: { x: number; y: number }) {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return null;
    return {
      left: Math.max(12, Math.min(rect.width - 12, screen.x - rect.left)),
      top: Math.max(12, Math.min(rect.height - 12, screen.y - rect.top)),
    };
  }

  function handleNodeClick(node: GraphNode, screen: { x: number; y: number }) {
    onSelectNode(node);
    setContextMenu(null);
    const xy = stageXY(screen);
    if (xy) setPopover({ node, ...xy });
  }

  async function handleNodeContextMenu(node: GraphNode, screen: { x: number; y: number }) {
    onSelectNode(node);
    setPopover(null);
    const xy = stageXY(screen);
    if (!xy) return;
    setContextMenu({ node, ...xy });
    setMenuTransforms([]);
    setMenuMachines([]);
    setMenuLoading(true);
    try {
      const [catalog, machines] = await Promise.all([listTransforms(node.type, true), listMachines(node.type).catch(() => [])]);
      setMenuTransforms(catalog.transforms);
      setMenuMachines(machines);
    } catch {
      setMenuTransforms([]);
    } finally {
      setMenuLoading(false);
    }
  }

  async function saveMachine(node: GraphNode) {
    const ids = menuTransforms.map((t) => t.id);
    if (ids.length === 0) return;
    const name = window.prompt("Machine name:", `${node.type} transform chain`);
    if (!name || !name.trim()) return;
    try {
      await createMachine({ name: name.trim(), transform_ids: ids, input_type: node.type });
      setMenuMachines(await listMachines(node.type).catch(() => []));
    } catch (err) {
      onError(err instanceof Error ? err.message : "The transform machine could not be saved.");
    }
  }

  function closeOverlays() {
    setPopover(null);
    setContextMenu(null);
  }

  function focusSearchResult(index: number) {
    if (searchResults.length === 0) return;
    const nextIndex = (index + searchResults.length) % searchResults.length;
    const node = searchResults[nextIndex];
    setSearchCursor(nextIndex);
    graphViewRef.current?.focusNode(node.id);
    onSelectNode(node);
  }

  async function removeSelectedEntities() {
    const selectedIds = graphViewRef.current?.getSelectedNodeIds() ?? [];
    const deletable = selectedIds.filter((id) => !id.startsWith("prepared-") && graph.nodes.some((node) => node.id === id));
    if (deletable.length === 0) return;
    const label = deletable.length === 1
      ? `Delete “${graph.nodes.find((node) => node.id === deletable[0])?.label ?? "selected entity"}” and its relationships?`
      : `Delete ${deletable.length} selected entities and their relationships?`;
    if (!window.confirm(label)) return;
    let deletedCount = 0;
    try {
      for (const entityId of deletable) {
        await deleteGraphEntity(entityId);
        deletedCount += 1;
      }
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not delete the selected entities");
    }
    if (deletedCount > 0) {
      graphViewRef.current?.clearSelection();
      onSelectNode(null);
      closeOverlays();
      try {
        await onGraphChanged();
      } catch (cause) {
        onError(cause instanceof Error ? cause.message : "The graph changed but could not be refreshed");
      }
    }
  }

  function handleStageKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement;
    const shortcut = resolveGraphShortcut({
      key: event.key,
      ctrlKey: event.ctrlKey,
      metaKey: event.metaKey,
      altKey: event.altKey,
      shiftKey: event.shiftKey,
      editable: Boolean(target.closest("input, textarea, select, [contenteditable='true']")),
    });
    if (shortcut === "dismiss-input") {
        searchInputRef.current?.blur();
        setSearchQuery("");
      return;
    }
    if (!shortcut) return;
    if (shortcut === "focus-search") {
      event.preventDefault();
      searchInputRef.current?.focus();
      return;
    }
    if (shortcut === "select-all") {
      event.preventDefault();
      graphViewRef.current?.selectAll();
      return;
    }
    if (shortcut === "undo" || shortcut === "redo") {
      event.preventDefault();
      if (shortcut === "redo") graphViewRef.current?.redo();
      else graphViewRef.current?.undo();
      return;
    }
    if (shortcut === "clear-selection") {
      graphViewRef.current?.clearSelection();
      onSelectNode(null);
      setSearchQuery("");
      closeOverlays();
      return;
    }
    if (shortcut === "delete-selection") {
      event.preventDefault();
      void removeSelectedEntities();
      return;
    }
    if (shortcut === "fit-view") {
      event.preventDefault();
      graphViewRef.current?.fitToView();
    }
  }

  const popoverNode = popover ? graph.nodes.find((n) => n.id === popover.node.id) ?? popover.node : null;
  const isPrepared = popoverNode?.id.startsWith("prepared-") ?? false;

  return (
    <div className="graph-panel graph-panel-featured">
      <GraphModeTabs value={graphView} onChange={setGraphView} />
      <div className="graph-tabbar">
        <div>
          <Network size={17} />
          <span>{activeGraphView.label}</span>
          <small>{filteredGraph.nodes.length} nodes · {filteredGraph.edges.length} relationships</small>
          <small className="graph-controls-hint">Drag to pin · drag background to pan · Shift-click for multi-select</small>
        </div>
        <div className="graph-tabbar-right">
          <div className="data-tools">
            <button type="button" title="Import entity CSV" onClick={() => csvInputRef.current?.click()} disabled={!caseId}>
              <Upload size={14} /> Import
            </button>
            <input ref={csvInputRef} type="file" accept=".csv,text/csv" hidden onChange={onCsvFile} />
            <div className="data-export">
              <button type="button" title="Export graph" onClick={() => setDataMenu((v) => !v)} disabled={!caseId}>
                <Download size={14} /> Export <ChevronDown size={12} />
              </button>
              {dataMenu && (
                <div className="data-export-menu" onPointerDown={(e) => e.stopPropagation()}>
                  <button type="button" onClick={exportPng}>PNG image</button>
                  <button type="button" onClick={() => downloadExport("graphml")}>GraphML (Gephi/yEd)</button>
                  <button type="button" onClick={() => downloadExport("csv-nodes")}>CSV · nodes</button>
                  <button type="button" onClick={() => downloadExport("csv-edges")}>CSV · edges</button>
                </div>
              )}
            </div>
          </div>
          <div className="view-switch">
            <button type="button" className={graphMode === "graph" ? "selected" : ""} onClick={() => setGraphMode("graph")}>Graph</button>
            <button type="button" className={graphMode === "table" ? "selected" : ""} onClick={() => setGraphMode("table")}>
              <Table2 size={14} />
              Table
            </button>
          </div>
        </div>
      </div>
      {showFilters && (
        <div className="graph-filterbar">
          <span>Type</span>
          {graphTypes.map((type) => (
            <button
              key={type}
              className={typeFilter === type ? "selected" : ""}
              type="button"
              onClick={() => setTypeFilter(type)}
            >
              {type === "all" ? "All" : type}
            </button>
          ))}
          <i />
          <span>Provenance</span>
          {(["all", "with-sources", "without-sources"] as const).map((filter) => (
            <button key={filter} className={sourceFilter === filter ? "selected" : ""} type="button" onClick={() => setSourceFilter(filter)}>
              {filter === "all" ? "All" : filter === "with-sources" ? "With sources" : "Without sources"}
            </button>
          ))}
          <small>{filteredGraph.nodes.length} visible nodes</small>
        </div>
      )}
      {graphMode === "graph" && <div className="graph-canvas-toolbar">
        <div className="graph-node-search">
          <Search size={13} />
          <input
            ref={searchInputRef}
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            onKeyDown={(event) => {
              if (resolveGraphShortcut({ key: event.key, editable: true }) === "dismiss-input") {
                event.currentTarget.blur();
                setSearchQuery("");
              }
            }}
            placeholder="Find label, ID, email, IP, alias…"
            aria-label="Find entity in graph"
          />
          {searchQuery && <span className="graph-search-count">{searchResults.length ? `${searchCursor + 1}/${searchResults.length}` : "0"}</span>}
          {searchResults.length > 0 && <>
            <button type="button" className="graph-search-step" onClick={() => focusSearchResult(searchCursor - 1)} aria-label="Previous graph search result"><ChevronUp size={12} /></button>
            <button type="button" className="graph-search-step" onClick={() => focusSearchResult(searchCursor + 1)} aria-label="Next graph search result"><ChevronDown size={12} /></button>
            <div className="graph-node-search-results">{searchResults.slice(0, 8).map((node, index) => <button type="button" key={node.id} className={index === searchCursor ? "active" : ""} onClick={() => focusSearchResult(index)}>{node.label}<small>{node.type} · {node.id}</small></button>)}</div>
          </>}
        </div>
        <button type="button" title="Zoom out" onClick={() => graphViewRef.current?.zoomBy(.82)}><Minus size={14} /></button>
        <button type="button" title="Zoom in" onClick={() => graphViewRef.current?.zoomBy(1.22)}><Plus size={14} /></button>
        <button type="button" title="Fit graph to screen" onClick={() => graphViewRef.current?.fitToView()}><Focus size={14} /></button>
        <button type="button" title="Run auto layout" onClick={() => graphViewRef.current?.resetLayout()}><Wand2 size={14} /></button>
        <span />
        <button type="button" title="Undo canvas change" onClick={() => graphViewRef.current?.undo()}><Undo2 size={14} /></button>
        <button type="button" title="Redo canvas change" onClick={() => graphViewRef.current?.redo()}><Redo2 size={14} /></button>
        <button type="button" className={showSnapshots ? "active" : ""} title="Layout snapshots" onClick={() => setShowSnapshots((value) => !value)}><Camera size={14} /> Snapshots</button>
        <button type="button" title="Save a named layout snapshot" onClick={() => void createSnapshot()}><Save size={14} /></button>
      </div>}
      {graphMode === "graph" ? (
        <div
          className="graph-stage"
          ref={stageRef}
          onPointerDown={closeOverlays}
          onKeyDown={handleStageKeyDown}
          style={{
            position: "relative",
            minHeight: "500px",
            overflow: "hidden",
          }}
        >
          <GraphView
            ref={graphViewRef}
            graph={sourceFilteredGraph}
            zoom={zoom}
            layoutVersion={layoutVersion}
            selectedNodeId={selectedNode?.id}
            typeFilter={typeFilter}
            viewMode={graphView}
            workspace={engineWorkspace}
            onWorkspaceChange={persistWorkspace}
            onSelectNode={onSelectNode}
            onOpenNode={onOpenNode}
            onNodeClick={handleNodeClick}
            onNodeContextMenu={handleNodeContextMenu}
          />

          {contextMenu && (
            <div
              className="node-menu"
              style={{ left: contextMenu.left, top: contextMenu.top }}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <button type="button" className="node-menu-item" onClick={() => { graphViewRef.current?.togglePinned(contextMenu.node.id); setPinVersion((value) => value + 1); setContextMenu(null); }}>
                {graphViewRef.current?.isPinned(contextMenu.node.id) ? <PinOff size={12} /> : <Pin size={12} />}
                <span className="node-menu-title">{graphViewRef.current?.isPinned(contextMenu.node.id) ? "Unpin position" : "Pin position"}</span>
              </button>
              <div className="node-menu-sep" />
              <div className="node-menu-head">
                <Wand2 size={12} />
                <span>Transforms · {getNodeConfig(contextMenu.node.type).label}</span>
              </div>
              {menuLoading && <div className="node-menu-empty">Loading…</div>}
              {!menuLoading && menuTransforms.length === 0 && (
                <div className="node-menu-empty">No transforms are available for this entity type.</div>
              )}
              {!menuLoading &&
                menuTransforms.map((transform) => (
                  <button
                    key={transform.id}
                    type="button"
                    className="node-menu-item"
                    disabled={expanding}
                    title={transform.description}
                    onClick={() => {
                      onRunTransform(transform.id, contextMenu.node);
                      setContextMenu(null);
                    }}
                  >
                    <Zap size={12} />
                    <span className="node-menu-title">{transform.title}</span>
                    <small className={transform.keyless ? "node-menu-tag" : "node-menu-tag key"}>
                      {transform.keyless ? transform.category : "key required"}
                    </small>
                  </button>
                ))}

              {!menuLoading && menuTransforms.length > 0 && (
                <>
                  <div className="node-menu-sep" />
                  <div className="node-menu-head">
                    <Layers size={12} />
                    <span>Transform machines</span>
                  </div>
                  <button
                    type="button"
                    className="node-menu-item machine-run"
                    disabled={expanding}
                    onClick={() => {
                      onRunAdhocMachine(menuTransforms.map((t) => t.id), contextMenu.node);
                      setContextMenu(null);
                    }}
                  >
                    <Play size={12} />
                    <span className="node-menu-title">Run all ({menuTransforms.length})</span>
                  </button>
                  <button type="button" className="node-menu-item" onClick={() => saveMachine(contextMenu.node)}>
                    <Save size={12} />
                    <span className="node-menu-title">Save as machine…</span>
                  </button>
                  {menuMachines.map((machine) => (
                    <button
                      key={machine.id}
                      type="button"
                      className="node-menu-item"
                      disabled={expanding}
                      title={`${machine.transform_ids.length} transforms`}
                      onClick={() => {
                        onRunSavedMachine(machine.id, contextMenu.node);
                        setContextMenu(null);
                      }}
                    >
                      <Layers size={12} />
                      <span className="node-menu-title">{machine.name}</span>
                      <small className="node-menu-tag">{machine.transform_ids.length}</small>
                    </button>
                  ))}
                </>
              )}
            </div>
          )}

          {popover && popoverNode && (
            <div
              className="node-card"
              style={{ left: popover.left, top: popover.top }}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <div className="node-card-head">
                <span className="node-card-dot" style={{ background: getNodeConfig(popoverNode.type).color }} />
                <div className="node-card-title">
                  <strong title={popoverNode.label}>{popoverNode.label}</strong>
                  <span>{getNodeConfig(popoverNode.type).label}</span>
                </div>
                <button type="button" className="node-card-close" onClick={() => setPopover(null)} aria-label="Close entity preview">
                  <X size={13} />
                </button>
              </div>
              <div className="node-card-meter" title={`Confidence ${score(popoverNode.confidence)}`}>
                <i style={{ width: `${Math.round(popoverNode.confidence * 100)}%`, background: getNodeConfig(popoverNode.type).color }} />
              </div>
              <div className="node-card-stats">
                <span>{score(popoverNode.confidence)} conf.</span>
                <span>{degree.get(popoverNode.id) ?? 0} connections</span>
                <span>{popoverNode.source_ids.length} sources</span>
              </div>
              {isPrepared ? (
                <p className="node-card-hint">Preview only — run the investigation before operating on this entity.</p>
              ) : (
                <div className="node-card-actions">
                  <button type="button" onClick={() => { onOpenNode(popoverNode); setPopover(null); }}>
                    <Maximize2 size={13} /> Open
                  </button>
                  <button type="button" onClick={() => { onExpandNode(popoverNode); }} disabled={expanding}>
                    {expanding ? <Loader2 size={13} className="ip-spin" /> : <Network size={13} />} Expand
                  </button>
                  {ENRICHABLE.has(popoverNode.type) && (
                    <button type="button" onClick={() => { onEnrichNode(popoverNode); }}>
                      <Globe size={13} /> Enrich
                    </button>
                  )}
                  <button type="button" onClick={() => { onConnectNode(popoverNode); setPopover(null); }}>
                    <Link2 size={13} /> Connect
                  </button>
                </div>
              )}
            </div>
          )}

          {showSnapshots && <aside className="graph-snapshots">
            <header><div><strong>Layout snapshots</strong><small>Named canvas states stored in SQLite</small></div><button type="button" onClick={() => setShowSnapshots(false)}><X size={13} /></button></header>
            {snapshots.length === 0 ? <p>No snapshots yet.</p> : snapshots.map((snapshot) => <div key={snapshot.id}><button type="button" onClick={() => void restoreSnapshot(snapshot)}><strong>{snapshot.name}</strong><small>{snapshot.node_count} nodes · {new Date(snapshot.created_at).toLocaleString()}</small></button><button type="button" title="Delete snapshot" onClick={() => void removeSnapshot(snapshot)}><Trash2 size={12} /></button></div>)}
          </aside>}

          {graphTypes.length > 1 && (
            <div className="graph-legend">
              {graphTypes
                .filter((type) => type !== "all")
                .map((type) => {
                  const cfg = getNodeConfig(type);
                  return (
                    <span key={type} className="legend-item">
                      <i style={{ background: cfg.color }} />
                      {cfg.label}
                    </span>
                  );
                })}
            </div>
          )}
          {graphAnalytics && (
            <div className="graph-metrics">
              <div>
                <span>Density</span>
                <strong>{Math.round(graphAnalytics.density * 1000) / 1000}</strong>
              </div>
              <div>
                <span>Components</span>
                <strong>{graphAnalytics.component_count}</strong>
              </div>
              <div>
                <span>Isolated</span>
                <strong>{graphAnalytics.isolated_node_count}</strong>
              </div>
              <div>
                <span>Bridges</span>
                <strong>{graphAnalytics.bridges.length}</strong>
              </div>
              {topHubs.length > 0 && (
                <div className="hub-strip">
                  {topHubs.map((hub) => (
                    <button
                      key={hub.entity_id}
                      type="button"
                      onClick={() => {
                        const node = graph.nodes.find((item) => item.id === hub.entity_id);
                        if (node) onOpenNode(node);
                      }}
                    >
                      {hub.label}
                      <small>{hub.degree}</small>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="graph-table">
          <table>
            <thead>
              <tr>
                <th>Entity</th>
                <th>Type</th>
                <th>Confidence</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filteredGraph.nodes.map((node) => (
                <tr key={node.id} className={node.id === selectedNode?.id ? "selected" : ""}>
                  <td>{node.label}</td>
                  <td>{node.type}</td>
                  <td>{score(node.confidence)}</td>
                  <td>
                    <button type="button" onClick={() => onOpenNode(node)}>
                      <Maximize2 size={14} />
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="edge-table">
            {filteredGraph.edges.map((edge) => (
              <div key={edge.id}>
                <span>{graph.nodes.find((node) => node.id === edge.source)?.label ?? edge.source} <strong>{edge.label}</strong> {graph.nodes.find((node) => node.id === edge.target)?.label ?? edge.target}</span>
                <small>{score(edge.confidence)}</small>
                <button type="button" onClick={() => void editRelationship(edge)}><Pencil size={12} /> Edit</button>
                <button type="button" onClick={() => void removeRelationship(edge)}><Trash2 size={12} /> Delete</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
