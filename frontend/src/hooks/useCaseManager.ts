import { useCallback, useEffect, useRef, useState } from "react";
import {
  getCaseMonitor,
  getApiUrl,
  getCustody,
  getGraph,
  getGraphAnalytics,
  getToken,
  listAuditEvents,
  listCases,
  listSearchHits,
  listSearchRuns,
  listSources,
  listTargetMemory,
  listTargetPhotos,
  listTargets,
} from "../api";
import type {
  AuditEvent,
  CaseMemory,
  CaseMonitor,
  CaseRead,
  CustodyReport,
  GraphAnalytics,
  GraphRead,
  SearchHit,
  SearchRun,
  SourceRead,
  TargetPhoto,
  TargetProfile,
} from "../types";
import { emptyGraph } from "../utils";

export interface CaseManagerState {
  cases: CaseRead[];
  activeCaseId: string;
  activeCase: CaseRead | undefined;
  targets: TargetProfile[];
  activeTargetId: string;
  activeTarget: TargetProfile | undefined;
  targetPhotos: TargetPhoto[];
  memory: CaseMemory[];
  runs: SearchRun[];
  latestRun: SearchRun | undefined;
  hits: SearchHit[];
  sources: SourceRead[];
  graph: GraphRead;
  custody: CustodyReport | null;
  monitor: CaseMonitor | null;
  auditEvents: AuditEvent[];
  graphAnalytics: GraphAnalytics | null;
}

export interface CaseManagerActions {
  setActiveCaseId: (id: string) => void;
  setActiveTargetId: (id: string) => void;
  setMemory: (m: CaseMemory[]) => void;
  setHits: (h: SearchHit[]) => void;
  setRuns: (r: SearchRun[]) => void;
  setTargetPhotos: (t: TargetPhoto[]) => void;
  setSources: (s: SourceRead[]) => void;
  setGraph: (g: GraphRead) => void;
  setCustody: (c: CustodyReport | null) => void;
  setMonitor: (m: CaseMonitor | null) => void;
  setAuditEvents: (a: AuditEvent[]) => void;
  setGraphAnalytics: (g: GraphAnalytics | null) => void;
  loadTargetContext: (caseId: string) => Promise<void>;
  refresh: (caseId?: string) => Promise<void>;
  openCase: (caseId: string) => Promise<void>;
}

export function useCaseManager(): CaseManagerState & CaseManagerActions {
  const [cases, setCases] = useState<CaseRead[]>([]);
  const [activeCaseId, setActiveCaseId] = useState("");
  const [targets, setTargets] = useState<TargetProfile[]>([]);
  const [activeTargetId, setActiveTargetId] = useState("");
  const [targetPhotos, setTargetPhotos] = useState<TargetPhoto[]>([]);
  const [memory, setMemory] = useState<CaseMemory[]>([]);
  const [runs, setRuns] = useState<SearchRun[]>([]);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [sources, setSources] = useState<SourceRead[]>([]);
  const [graph, setGraph] = useState<GraphRead>(emptyGraph);
  const [custody, setCustody] = useState<CustodyReport | null>(null);
  const [monitor, setMonitor] = useState<CaseMonitor | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [graphAnalytics, setGraphAnalytics] = useState<GraphAnalytics | null>(null);
  const refreshGeneration = useRef(0);

  const activeCase = cases.find((item) => item.id === activeCaseId);
  const activeTarget = targets.find((item) => item.id === activeTargetId);
  const latestRun = runs[0];

  const clearCaseContext = useCallback(() => {
    setTargets([]);
    setActiveTargetId("");
    setMemory([]);
    setRuns([]);
    setHits([]);
    setTargetPhotos([]);
    setSources([]);
    setGraph(emptyGraph);
    setCustody(null);
    setMonitor(null);
    setAuditEvents([]);
    setGraphAnalytics(null);
  }, []);

  const loadTargetContextForGeneration = useCallback(async (caseId: string, generation: number) => {
    const [
      nextSources,
      nextGraph,
      nextTargets,
      nextCustody,
      nextMonitor,
      nextAuditEvents,
      nextGraphAnalytics,
    ] = await Promise.all([
      listSources(caseId),
      getGraph(caseId),
      listTargets(caseId),
      getCustody(caseId).catch(() => null),
      getCaseMonitor(caseId).catch(() => null),
      listAuditEvents(caseId, 40).catch(() => []),
      getGraphAnalytics(caseId).catch(() => null),
    ]);
    if (generation !== refreshGeneration.current) return;
    const selectedTarget = nextTargets[0]?.id || "";
    let nextMemory: CaseMemory[] = [];
    let nextRuns: SearchRun[] = [];
    let nextPhotos: TargetPhoto[] = [];
    let nextHits: SearchHit[] = [];
    if (selectedTarget) {
      [nextMemory, nextRuns, nextPhotos] = await Promise.all([
        listTargetMemory(selectedTarget),
        listSearchRuns(selectedTarget),
        listTargetPhotos(selectedTarget),
      ]);
      if (nextRuns[0]) {
        nextHits = await listSearchHits(nextRuns[0].id);
      }
    }
    if (generation !== refreshGeneration.current) return;

    setSources(nextSources);
    setGraph(nextGraph);
    setTargets(nextTargets);
    setCustody(nextCustody);
    setMonitor(nextMonitor);
    setAuditEvents(nextAuditEvents);
    setGraphAnalytics(nextGraphAnalytics);
    setActiveTargetId(selectedTarget);
    setMemory(nextMemory);
    setRuns(nextRuns);
    setTargetPhotos(nextPhotos);
    setHits(nextHits);
  }, []);

  const loadTargetContext = useCallback(
    async (caseId: string) => {
      const generation = ++refreshGeneration.current;
      if (caseId !== activeCaseId) {
        clearCaseContext();
        setActiveCaseId(caseId);
      }
      await loadTargetContextForGeneration(caseId, generation);
    },
    [activeCaseId, clearCaseContext, loadTargetContextForGeneration],
  );

  const refresh = useCallback(
    async (caseId?: string) => {
      const generation = ++refreshGeneration.current;
      const switchingCase = Boolean(caseId && caseId !== activeCaseId);
      if (switchingCase) {
        clearCaseContext();
        setActiveCaseId(caseId || "");
      }
      const nextCases = await listCases();
      if (generation !== refreshGeneration.current) return;
      setCases(nextCases);
      const selected = caseId
        || (nextCases.some((item) => item.id === activeCaseId) ? activeCaseId : nextCases[0]?.id)
        || "";
      if (!switchingCase && selected !== activeCaseId) clearCaseContext();
      setActiveCaseId(selected);
      if (selected) {
        await loadTargetContextForGeneration(selected, generation);
      }
    },
    [activeCaseId, clearCaseContext, loadTargetContextForGeneration],
  );

  const openCase = useCallback(
    async (caseId: string) => {
      await refresh(caseId);
    },
    [refresh],
  );

  // WebSocket subscription for live updates
  useEffect(() => {
    if (!activeCaseId) return;
    const token = getToken();
    if (!token) return;
    const wsUrl = `${getApiUrl().replace(/^http/, "ws")}/ws/cases/${activeCaseId}?token=${encodeURIComponent(token)}`;
    const socket = new WebSocket(wsUrl);
    socket.onmessage = () => refresh(activeCaseId);
    return () => socket.close();
  }, [activeCaseId, refresh]);

  return {
    cases,
    activeCaseId,
    activeCase,
    targets,
    activeTargetId,
    activeTarget,
    targetPhotos,
    memory,
    runs,
    latestRun,
    hits,
    sources,
    graph,
    custody,
    monitor,
    auditEvents,
    graphAnalytics,
    setActiveCaseId,
    setActiveTargetId,
    setMemory,
    setHits,
    setRuns,
    setTargetPhotos,
    setSources,
    setGraph,
    setCustody,
    setMonitor,
    setAuditEvents,
    setGraphAnalytics,
    loadTargetContext,
    refresh,
    openCase,
  };
}
