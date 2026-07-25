import { useCallback, useState } from "react";
import {
  createGraphEntity,
  expandEntity,
  importGraphCsv,
  osintLookup,
  promoteOsintQuery,
  runAdhocMachine,
  runMachine,
  runTransform,
} from "../api";
import type {
  GraphNode,
  ManualEntityForm,
} from "../types";

export interface GraphInteractionState {
  selectedNode: GraphNode | null;
  openedNode: GraphNode | null;
  expanding: boolean;
  pivotInfo: string;
  graphZoom: number;
  layoutVersion: number;
  showFilters: boolean;
  manualEntity: ManualEntityForm;
}

export interface GraphInteractionActions {
  setSelectedNode: (n: GraphNode | null) => void;
  setOpenedNode: (n: GraphNode | null) => void;
  setExpanding: (v: boolean) => void;
  setPivotInfo: (v: string) => void;
  setGraphZoom: (v: number) => void;
  setLayoutVersion: (v: number) => void;
  setShowFilters: (v: boolean) => void;
  setManualEntity: (f: ManualEntityForm) => void;
  patchManualEntity: (patch: Partial<ManualEntityForm>) => void;
  openNode: (node: GraphNode) => void;
  handleNodeRenamed: (updated: GraphNode) => void;
  expandNode: (node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => Promise<void>;
  enrichNode: (node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => Promise<void>;
  importCsv: (csv: string, activeCaseId: string, refresh: () => Promise<void>, onError: (msg: string) => void) => Promise<void>;
  runTransformOnNode: (transformId: string, node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => Promise<void>;
  runAdhocMachineOnNode: (transformIds: string[], node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => Promise<void>;
  runSavedMachineOnNode: (machineId: string, node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => Promise<void>;
  addManualEntity: (event: React.FormEvent, activeCaseId: string, selectedNode: GraphNode | null, refresh: () => Promise<void>) => Promise<void>;
  focusGraph: (canvasGraph: { nodes: GraphNode[] }) => void;
  resetLayout: () => void;
}

const defaultManualEntity: ManualEntityForm = {
  label: "",
  type: "handle",
  confidence: 0.68,
  relation_label: "analyst_linked",
};

export function useGraphInteraction(): GraphInteractionState & GraphInteractionActions {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [openedNode, setOpenedNode] = useState<GraphNode | null>(null);
  const [expanding, setExpanding] = useState(false);
  const [pivotInfo, setPivotInfo] = useState("");
  const [graphZoom, setGraphZoom] = useState(1);
  const [layoutVersion, setLayoutVersion] = useState(0);
  const [showFilters, setShowFilters] = useState(false);
  const [manualEntity, setManualEntity] = useState<ManualEntityForm>(defaultManualEntity);

  const patchManualEntity = useCallback((patch: Partial<ManualEntityForm>) => {
    setManualEntity((prev) => ({ ...prev, ...patch }));
  }, []);

  const openNode = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    setOpenedNode(node);
  }, []);

  const handleNodeRenamed = useCallback((updated: GraphNode) => {
    setOpenedNode(updated);
    setSelectedNode((prev) => (prev?.id === updated.id ? updated : prev));
  }, []);

  const expandNode = useCallback(
    async (node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => {
      if (!activeCaseId || node.id.startsWith("prepared-")) return;
      setExpanding(true);
      setPivotInfo("");
      try {
        const result = await expandEntity(node.id);
        setPivotInfo(`${result.strategy} · +${result.new_nodes.length} nodos — ${result.summary}`);
        await refresh();
      } finally {
        setExpanding(false);
      }
    },
    [],
  );

  const enrichNode = useCallback(
    async (node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => {
      if (!activeCaseId || node.id.startsWith("prepared-")) return;
      setExpanding(true);
      setPivotInfo("");
      try {
        const lookup = await osintLookup({ case_id: activeCaseId, value: node.label });
        const result = await promoteOsintQuery(lookup.query_id);
        setPivotInfo(`OSINT · ${result.summary}`);
        await refresh();
      } finally {
        setExpanding(false);
      }
    },
    [],
  );

  const importCsvAction = useCallback(
    async (csv: string, activeCaseId: string, refresh: () => Promise<void>, onError: (msg: string) => void) => {
      if (!activeCaseId) {
        onError("Abre o crea un caso antes de importar.");
        return;
      }
      setPivotInfo("");
      const result = await importGraphCsv(activeCaseId, csv);
        setPivotInfo(
          `Import CSV · +${result.nodes} nodos, +${result.edges} aristas` +
            (result.errors.length ? ` (${result.errors.length} filas con error)` : ""),
        );
      await refresh();
    },
    [],
  );

  const runTransformOnNode = useCallback(
    async (transformId: string, node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => {
      if (!activeCaseId || node.id.startsWith("prepared-")) return;
      setExpanding(true);
      setPivotInfo("");
      try {
        const result = await runTransform(transformId, node.id);
        setPivotInfo(`${result.summary} · +${result.new_nodes.length} nodos`);
        await refresh();
      } finally {
        setExpanding(false);
      }
    },
    [],
  );

  const runAdhocMachineOnNode = useCallback(
    async (transformIds: string[], node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => {
      if (!activeCaseId || node.id.startsWith("prepared-")) return;
      setExpanding(true);
      setPivotInfo("");
      try {
        const result = await runAdhocMachine(transformIds, node.id);
        setPivotInfo(result.summary);
        await refresh();
      } finally {
        setExpanding(false);
      }
    },
    [],
  );

  const runSavedMachineOnNode = useCallback(
    async (machineId: string, node: GraphNode, activeCaseId: string, refresh: () => Promise<void>) => {
      if (!activeCaseId || node.id.startsWith("prepared-")) return;
      setExpanding(true);
      setPivotInfo("");
      try {
        const result = await runMachine(machineId, node.id);
        setPivotInfo(result.summary);
        await refresh();
      } finally {
        setExpanding(false);
      }
    },
    [],
  );

  const addManualEntity = useCallback(
    async (
      event: React.FormEvent,
      activeCaseId: string,
      selectedNode: GraphNode | null,
      refresh: () => Promise<void>,
    ) => {
      event.preventDefault();
      if (!activeCaseId || !manualEntity.label.trim()) return;
      const node = await createGraphEntity({
          case_id: activeCaseId,
          label: manualEntity.label.trim(),
          type: manualEntity.type,
          confidence: manualEntity.confidence,
          connect_to_id: selectedNode?.id?.startsWith("prepared-") ? null : selectedNode?.id ?? null,
          relation_label: manualEntity.relation_label,
        });
        patchManualEntity({ label: "" });
        setSelectedNode(node);
        setOpenedNode(node);
      await refresh();
    },
    [manualEntity, patchManualEntity],
  );

  const focusGraph = useCallback((canvasGraph: { nodes: GraphNode[] }) => {
    const focusNode = canvasGraph.nodes.find((node) => node.type === "name") ?? canvasGraph.nodes[0] ?? null;
    setSelectedNode(focusNode);
    setOpenedNode(focusNode);
    setGraphZoom(1.12);
  }, []);

  const resetLayout = useCallback(() => {
    setLayoutVersion((prev) => prev + 1);
    setGraphZoom(1);
  }, []);

  return {
    selectedNode,
    openedNode,
    expanding,
    pivotInfo,
    graphZoom,
    layoutVersion,
    showFilters,
    manualEntity,
    setSelectedNode,
    setOpenedNode,
    setExpanding,
    setPivotInfo,
    setGraphZoom,
    setLayoutVersion,
    setShowFilters,
    setManualEntity,
    patchManualEntity,
    openNode,
    handleNodeRenamed,
    expandNode,
    enrichNode,
    importCsv: importCsvAction,
    runTransformOnNode,
    runAdhocMachineOnNode,
    runSavedMachineOnNode,
    addManualEntity,
    focusGraph,
    resetLayout,
  };
}
