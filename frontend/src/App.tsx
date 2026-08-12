import { useCallback, useEffect, useState } from "react";
import { createCase, deleteCase, downloadCaseExport, duplicateCase, getApplicationSettings, getLocalModelRuntimeStatus, getStorageStatus, importCaseDocument, rerunTargetSearch, saveApplicationSettings, updateCase } from "./api";
import { isCaseScopedArea, isModuleRouteId, type PlatformArea } from "./app/navigation";
import { PlatformShell } from "./app/PlatformShell";
import { usePlatformRoute } from "./app/usePlatformRoute";
import { DashboardView } from "./features/dashboard/DashboardView";
import { EntityManagerView } from "./features/entities/EntityManagerView";
import { EvidenceVaultView } from "./features/evidence/EvidenceVaultView";
import { CopilotWorkspaceView } from "./features/copilot/CopilotWorkspaceView";
import { GraphWorkspaceView } from "./features/graph/GraphWorkspaceView";
import { InvestigationsView } from "./features/investigations/InvestigationsView";
import { NewInvestigationDialog } from "./features/investigations/NewInvestigationDialog";
import { ReportsWorkspaceView } from "./features/reports/ReportsWorkspaceView";
import { LocalModelsView } from "./features/models/LocalModelsView";
import { DataSourcesView } from "./features/sources/DataSourcesView";
import { OsintWorkspaceView } from "./features/osint/OsintWorkspaceView";
import { AboutView } from "./features/about/AboutView";
import { SettingsView } from "./features/settings/SettingsView";
import { OnboardingDialog } from "./features/onboarding/OnboardingDialog";
import { usePlatformCatalogs } from "./features/settings/usePlatformCatalogs";
import { TimelineView } from "./features/timeline";
import { ToolsWorkspaceView } from "./features/tools/ToolsWorkspaceView";
import { useUpdater } from "./features/updates/useUpdater";
import { useCaseManager } from "./hooks/useCaseManager";
import { useGraphInteraction } from "./hooks/useGraphInteraction";
import { EmptyState } from "./shared/ui/EmptyState";
import { WorkspaceHeader } from "./shared/ui/WorkspaceHeader";
import { SystemLinkControlPlane } from "./system-link/components/SystemLinkControlPlane";
import { SystemLinkModuleView } from "./system-link/components/SystemLinkModuleView";
import { useSystemLinkRegistry } from "./system-link/registry";
import type { ApplicationSettings, CaseRead, DesktopStatus, GraphNode, InvestigationDraft, LocalModelRuntimeStatus, StorageStatus, User } from "./types";

export function App({ currentUser }: { currentUser: User }) {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [desktopStatus, setDesktopStatus] = useState<DesktopStatus | null>(null);
  const [showNewCase, setShowNewCase] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [applicationSettings, setApplicationSettings] = useState<ApplicationSettings | null>(null);
  const [storageStatus, setStorageStatus] = useState<StorageStatus | null>(null);
  const [localModelStatus, setLocalModelStatus] = useState<LocalModelRuntimeStatus | null>(null);
  const [localModelLoading, setLocalModelLoading] = useState(true);
  const [settingsError, setSettingsError] = useState("");

  const systemLink = useSystemLinkRegistry();
  const { route, navigate, navigateCase } = usePlatformRoute(systemLink.moduleNavigation);
  const caseMgr = useCaseManager();
  const graph = useGraphInteraction();
  const catalogs = usePlatformCatalogs();
  const updater = useUpdater(
    applicationSettings?.general.check_updates ?? false,
    applicationSettings?.general.update_channel ?? "alpha",
    desktopStatus?.updater_enabled ?? false,
  );

  const activeCaseId = caseMgr.activeCaseId;
  const activeCase = !route.caseId || route.caseId === activeCaseId ? caseMgr.activeCase : undefined;
  const refreshCases = caseMgr.refresh;
  const selectedNode = graph.selectedNode;
  const setSelectedNode = graph.setSelectedNode;
  const setOpenedNode = graph.setOpenedNode;

  const setSafeError = useCallback((message: string) => {
    setError(message);
    if (message) window.setTimeout(() => setError(""), 6000);
  }, []);

  const canvasGraph = caseMgr.graph;

  useEffect(() => {
    if ((!route.caseId && activeCaseId) || (Boolean(route.caseId) && route.caseId === activeCaseId)) return;
    refreshCases(route.caseId || undefined).catch((cause) => {
      setSafeError(cause instanceof Error ? cause.message : "Could not load investigations");
    });
  }, [activeCaseId, refreshCases, route.caseId, setSafeError]);

  useEffect(() => {
    if (selectedNode && canvasGraph.nodes.some((node) => node.id === selectedNode.id)) return;
    const first = canvasGraph.nodes[0] ?? null;
    setSelectedNode(first);
    setOpenedNode(null);
  }, [canvasGraph.nodes, selectedNode, setOpenedNode, setSelectedNode]);

  useEffect(() => {
    if (!("__TAURI_INTERNALS__" in window)) return;
    import("@tauri-apps/api/core")
      .then(({ invoke }) => invoke<DesktopStatus>("desktop_status"))
      .then(setDesktopStatus)
      .catch(() => setDesktopStatus(null));
  }, []);

  const handleNavigate = useCallback(
    (area: PlatformArea) => {
      if (isCaseScopedArea(area, systemLink.moduleNavigation) && !activeCaseId) {
        navigate("investigations");
        return;
      }
      navigate(area, activeCaseId);
    },
    [activeCaseId, navigate, systemLink.moduleNavigation],
  );

  const openNewCaseDialog = useCallback(() => {
    setShowNewCase(true);
  }, []);

  const refreshApplicationSettings = useCallback(async () => {
    setSettingsError("");
    try {
      const [preferences, storage] = await Promise.all([getApplicationSettings(), getStorageStatus()]);
      setApplicationSettings(preferences);
      setStorageStatus(storage);
      return preferences;
    } catch (cause) {
      setSettingsError(cause instanceof Error ? cause.message : "Could not load local settings");
      return null;
    }
  }, []);

  useEffect(() => {
    void refreshApplicationSettings().then((preferences) => {
      if (preferences && !preferences.onboarding_complete) setShowOnboarding(true);
    });
  }, [refreshApplicationSettings]);

  const refreshLocalModelStatus = useCallback(async () => {
    setLocalModelLoading(true);
    try {
      setLocalModelStatus(await getLocalModelRuntimeStatus());
    } catch {
      setLocalModelStatus({
        configured: false,
        connected: false,
        provider: "",
        endpoint: "",
        model: "",
        model_available: false,
        model_count: 0,
        context_length: null,
        max_tokens: null,
        latency_ms: null,
        error: "StatusUnavailable",
      });
    } finally {
      setLocalModelLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshLocalModelStatus();
  }, [refreshLocalModelStatus]);

  useEffect(() => {
    if (!applicationSettings) return;
    document.documentElement.style.fontSize = `${applicationSettings.appearance.text_scale * 100}%`;
    document.documentElement.dataset.density = applicationSettings.appearance.density;
    document.documentElement.classList.toggle("reduce-motion", applicationSettings.appearance.reduce_motion);
  }, [applicationSettings]);

  const openCase = useCallback((caseId: string) => {
    if (caseId) navigateCase(caseId);
  }, [navigateCase]);

  const createInvestigation = async (draft: InvestigationDraft) => {
    setLoading(true);
    setError("");
    try {
      const result = await createCase(draft);
      setShowNewCase(false);
      await caseMgr.refresh(result.id);
      navigate("investigations", result.id);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not create investigation");
    } finally {
      setLoading(false);
    }
  };

  const createOnboardingInvestigation = async (draft: InvestigationDraft): Promise<CaseRead> => {
    const result = await createCase(draft);
    await caseMgr.refresh(result.id);
    return result;
  };

  const persistApplicationSettings = async (next: ApplicationSettings) => {
    const saved = await saveApplicationSettings({
      onboarding_complete: next.onboarding_complete,
      general: next.general,
      appearance: next.appearance,
      storage: next.storage,
      tools: next.tools,
      privacy: next.privacy,
      performance: next.performance,
    });
    setApplicationSettings(saved);
  };

  const completeOnboarding = async () => {
    if (applicationSettings) {
      await persistApplicationSettings({ ...applicationSettings, onboarding_complete: true });
    }
    setShowOnboarding(false);
    navigate("dashboard");
  };

  const mutateInvestigation = async (action: () => Promise<unknown>, preferredId?: string) => {
    setLoading(true);
    setError("");
    try {
      await action();
      await caseMgr.refresh(preferredId);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not update investigation");
    } finally {
      setLoading(false);
    }
  };

  const exportInvestigation = async (caseId: string, title: string) => {
    try {
      const blob = await downloadCaseExport(caseId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${title.replace(/[^a-z0-9_-]+/gi, "_") || "investigation"}.oihk.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not export investigation");
    }
  };

  const editInvestigation = async (caseId: string, draft: InvestigationDraft) => {
    await mutateInvestigation(() => updateCase(caseId, draft), caseId);
  };

  const setInvestigationStatus = async (caseId: string, status: "active" | "archived") => {
    await mutateInvestigation(() => updateCase(caseId, { status }), caseId);
  };

  const duplicateInvestigation = async (caseId: string) => {
    setLoading(true);
    try {
      const result = await duplicateCase(caseId);
      await caseMgr.refresh(result.id);
      navigate("investigations", result.id);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not duplicate investigation");
    } finally {
      setLoading(false);
    }
  };

  const removeInvestigation = async (caseId: string) => {
    setLoading(true);
    try {
      await deleteCase(caseId);
      navigate("investigations");
      await caseMgr.refresh();
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not delete investigation");
    } finally {
      setLoading(false);
    }
  };

  const importInvestigation = async (document: unknown) => {
    setLoading(true);
    try {
      const result = await importCaseDocument(document);
      await caseMgr.refresh(result.id);
      navigate("investigations", result.id);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not import investigation");
    } finally {
      setLoading(false);
    }
  };

  const runAgain = async () => {
    if (!caseMgr.activeTargetId) return;
    setLoading(true);
    setError("");
    try {
      const result = await rerunTargetSearch(caseMgr.activeTargetId);
      caseMgr.setMemory(result.memory);
      caseMgr.setHits(result.hits);
      caseMgr.setTargetPhotos(result.photos);
      if (result.search_run) caseMgr.setRuns([result.search_run, ...caseMgr.runs]);
      await caseMgr.refresh(result.case.id);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not rerun discovery");
    } finally {
      setLoading(false);
    }
  };

  const refreshActiveCase = useCallback(async () => {
    if (activeCaseId) await refreshCases(activeCaseId);
  }, [activeCaseId, refreshCases]);

  const expandNode = async (node: GraphNode) => {
    try {
      await graph.expandNode(node, caseMgr.activeCaseId, refreshActiveCase);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not expand entity");
    }
  };

  const enrichNode = async (node: GraphNode) => {
    try {
      await graph.enrichNode(node, caseMgr.activeCaseId, refreshActiveCase);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not enrich entity");
    }
  };

  const importCsv = async (csv: string) => {
    try {
      await graph.importCsv(csv, caseMgr.activeCaseId, refreshActiveCase, setSafeError);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not import CSV");
    }
  };

  const addManualEntity = async (event: React.FormEvent) => {
    try {
      await graph.addManualEntity(event, caseMgr.activeCaseId, graph.selectedNode, refreshActiveCase);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not add entity");
    }
  };

  const runTransformOnNode = async (transformId: string, node: GraphNode) => {
    try {
      await graph.runTransformOnNode(transformId, node, caseMgr.activeCaseId, refreshActiveCase);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Transform failed");
    }
  };

  const runAdhocMachineOnNode = async (transformIds: string[], node: GraphNode) => {
    try {
      await graph.runAdhocMachineOnNode(transformIds, node, caseMgr.activeCaseId, refreshActiveCase);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Transform chain failed");
    }
  };

  const runSavedMachineOnNode = async (machineId: string, node: GraphNode) => {
    try {
      await graph.runSavedMachineOnNode(machineId, node, caseMgr.activeCaseId, refreshActiveCase);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Saved machine failed");
    }
  };

  const caseRequired = isCaseScopedArea(route.area, systemLink.moduleNavigation) && !activeCase;
  let content: React.ReactNode;

  if (caseRequired) {
    content = (
      <div className="platform-view">
        <WorkspaceHeader
          eyebrow="Investigation required"
          title="Open an investigation"
          description="This workspace is case-scoped and cannot display organization-wide or synthetic data."
        />
        <EmptyState
          title="No active investigation"
          description="Choose an authorized investigation or create a new one."
          action={<button onClick={() => navigate("investigations")}>View investigations</button>}
        />
      </div>
    );
  } else {
    switch (route.area) {
      case "dashboard":
        content = (
          <DashboardView
            refreshKey={`${caseMgr.cases.map((item) => `${item.id}:${item.status}:${item.updated_at}`).join("|")}:${caseMgr.auditEvents[0]?.id ?? 0}`}
            storageStatus={storageStatus}
            localModelStatus={localModelStatus}
            localModelLoading={localModelLoading}
            onRefreshLocalModel={() => void refreshLocalModelStatus()}
            onNavigate={handleNavigate}
            onOpenCase={(caseId) => void openCase(caseId)}
            onNewCase={openNewCaseDialog}
          />
        );
        break;
      case "investigations":
        content = (
          <InvestigationsView
            cases={caseMgr.cases}
            activeCase={activeCase}
            monitor={caseMgr.monitor}
            loading={loading}
            canRerun={Boolean(caseMgr.activeTargetId)}
            onOpenCase={(caseId) => void openCase(caseId)}
            onNewCase={openNewCaseDialog}
            onRunAgain={() => void runAgain()}
            onOpenWorkspace={() => handleNavigate("graph")}
            onEdit={editInvestigation}
            onDuplicate={duplicateInvestigation}
            onSetStatus={setInvestigationStatus}
            onDelete={removeInvestigation}
            onExport={exportInvestigation}
            onImport={importInvestigation}
          />
        );
        break;
      case "entities":
        content = (
          <EntityManagerView
            nodes={caseMgr.graph.nodes}
            selectedNode={graph.selectedNode}
            onSelectNode={graph.openNode}
            onRefresh={refreshActiveCase}
            onOpenGraph={() => handleNavigate("graph")}
            onError={setSafeError}
          />
        );
        break;
      case "evidence":
        content = (
          <EvidenceVaultView
            caseId={caseMgr.activeCaseId}
            sources={caseMgr.sources}
            photos={caseMgr.targetPhotos}
            custody={caseMgr.custody}
            entities={caseMgr.graph.nodes}
            onRefresh={refreshActiveCase}
          />
        );
        break;
      case "timeline":
        content = (
          <div className="platform-view">
            <WorkspaceHeader
              eyebrow="Derived investigation activity"
              title="Timeline"
              description="A real chronological projection of audit events, collected sources, search runs, and hashed uploads."
            />
            <p className="platform-footnote">
              Manual events and comments are not available until the canonical investigation-event API is implemented.
            </p>
            <TimelineView
              auditEvents={caseMgr.auditEvents}
              sources={caseMgr.sources}
              searchRuns={caseMgr.runs}
              targetPhotos={caseMgr.targetPhotos}
              exportFileName={`${activeCase?.title?.replace(/[^a-z0-9_-]+/gi, "_") || "investigation"}-timeline.json`}
            />
          </div>
        );
        break;
      case "graph":
        content = (
          <GraphWorkspaceView
            graph={canvasGraph}
            analytics={caseMgr.graphAnalytics}
            selectedNode={graph.selectedNode}
            openedNode={graph.openedNode}
            zoom={graph.graphZoom}
            layoutVersion={graph.layoutVersion}
            showFilters={graph.showFilters}
            expanding={graph.expanding}
            caseId={caseMgr.activeCaseId}
            manualEntity={graph.manualEntity}
            onManualEntityChange={graph.patchManualEntity}
            onAddEntity={(event) => void addManualEntity(event)}
            onSelectNode={graph.setSelectedNode}
            onOpenNode={graph.openNode}
            onCloseInspector={() => {
              graph.setSelectedNode(null);
              graph.setOpenedNode(null);
            }}
            onExpandNode={(node) => void expandNode(node)}
            onEnrichNode={(node) => void enrichNode(node)}
            onRunTransform={(transformId, node) => void runTransformOnNode(transformId, node)}
            onRunAdhocMachine={(transformIds, node) => void runAdhocMachineOnNode(transformIds, node)}
            onRunSavedMachine={(machineId, node) => void runSavedMachineOnNode(machineId, node)}
            onImportCsv={(csv) => void importCsv(csv)}
            onGraphChanged={refreshActiveCase}
            onToggleFilters={() => graph.setShowFilters(!graph.showFilters)}
            onResetLayout={graph.resetLayout}
            onOpenEntityManager={() => handleNavigate("entities")}
            onError={setSafeError}
          />
        );
        break;
      case "tools":
        content = (
          <ToolsWorkspaceView
            caseId={caseMgr.activeCaseId}
            isAdmin={currentUser.role === "admin" || currentUser.role === "system"}
            sources={caseMgr.sources}
            custody={caseMgr.custody}
            onRefresh={refreshActiveCase}
            onOpenEvidence={() => handleNavigate("evidence")}
          />
        );
        break;
      case "reports":
        content = activeCase ? (
          <ReportsWorkspaceView
            activeCase={activeCase}
            graph={caseMgr.graph}
            sources={caseMgr.sources}
            custody={caseMgr.custody}
          />
        ) : null;
        break;
      case "copilot":
        content = (
          <CopilotWorkspaceView
            caseId={caseMgr.activeCaseId}
            targetId={caseMgr.activeTargetId}
            onOpenModels={() => handleNavigate("models")}
          />
        );
        break;
      case "osint":
        content = (
          <OsintWorkspaceView
            caseId={caseMgr.activeCaseId}
            onGraphChanged={refreshActiveCase}
            onOpenGraph={() => handleNavigate("graph")}
          />
        );
        break;
      case "models":
        content = <LocalModelsView onStatusChanged={() => void refreshLocalModelStatus()} />;
        break;
      case "sources":
        content = (
          <DataSourcesView
            activeCase={activeCase}
            sources={caseMgr.sources}
            onOpenEvidence={() => handleNavigate("evidence")}
            onOpenInvestigations={() => handleNavigate("investigations")}
          />
        );
        break;
      case "settings":
        content = (
          <SettingsView
            user={currentUser}
            desktopStatus={desktopStatus}
            providers={catalogs.providers}
            settings={applicationSettings}
            storage={storageStatus}
            loading={catalogs.loading || loading}
            error={settingsError || catalogs.error}
            onRefresh={() => void Promise.all([catalogs.refresh(), refreshApplicationSettings()])}
            onSave={persistApplicationSettings}
            onRunOnboarding={() => setShowOnboarding(true)}
            onOpenModels={() => handleNavigate("models")}
            onOpenSystemLink={() => handleNavigate("system-link")}
            updater={updater}
          />
        );
        break;
      case "system-link":
        content = <SystemLinkControlPlane registry={systemLink} onNavigate={handleNavigate} />;
        break;
      case "about":
        content = <AboutView desktopStatus={desktopStatus} updater={updater} />;
        break;
      default:
        content = isModuleRouteId(route.area)
          ? <SystemLinkModuleView route={route.area} modules={systemLink.status?.modules ?? []} activeCaseId={caseMgr.activeCaseId ?? undefined} />
          : null;
        break;
    }
  }

  return (
    <>
      <PlatformShell
        area={route.area}
        cases={caseMgr.cases}
        activeCase={activeCase}
        currentUser={currentUser}
        desktopStatus={desktopStatus}
        storageStatus={storageStatus}
        localModelStatus={localModelStatus}
        localModelLoading={localModelLoading}
        systemLinkStatus={systemLink.status}
        moduleNavigation={systemLink.moduleNavigation}
        loading={loading}
        error={error}
        onNavigate={handleNavigate}
        onOpenCase={(caseId) => void openCase(caseId)}
        onNewCase={openNewCaseDialog}
        onDismissError={() => setError("")}
      >
        {content}
      </PlatformShell>
      <NewInvestigationDialog
        open={showNewCase}
        loading={loading}
        onClose={() => setShowNewCase(false)}
        onSubmit={createInvestigation}
      />
      <OnboardingDialog
        open={showOnboarding}
        settings={applicationSettings}
        cases={caseMgr.cases}
        onComplete={completeOnboarding}
        onCreateCase={createOnboardingInvestigation}
        onLocalModelStatusChanged={() => void refreshLocalModelStatus()}
        onOpenModels={() => { setShowOnboarding(false); handleNavigate("models"); }}
      />
    </>
  );
}
