import React, { useCallback, useEffect, useState } from "react";
import { downloadReport, listCases, listSources, getGraph, getGraphAnalytics, getCustody, targetIntake, listAuditEvents, getCaseMonitor } from "./api";
import type { CaseRead, GraphNode, SourceRead, TargetIntakeResult, CaseMemory, SearchHit, SearchRun, TargetPhoto, CaseMonitor, AuditEvent, GraphRead, GraphAnalytics, CustodyReport, User } from "./types";
import { InvestigationsView } from "./features/investigations/InvestigationsView";
import { EntityManagerView } from "./features/entities/EntityManagerView";
import { EvidenceVaultView } from "./features/evidence/EvidenceVaultView";
import { GraphWorkspaceView } from "./features/graph/GraphWorkspaceView";
import { ReportsWorkspaceView } from "./features/reports/ReportsWorkspaceView";
import { SettingsView } from "./features/settings/SettingsView";
import { ToolsWorkspaceView } from "./features/tools/ToolsWorkspaceView";
import { TimelineView } from "./features/timeline/TimelineView";
import { DashboardView } from "./features/dashboard/DashboardView";
import { NewInvestigationDialog } from "./features/investigations/NewInvestigationDialog";
import { WorkspaceHeader } from "./shared/ui/WorkspaceHeader";
import { EmptyState } from "./shared/ui/EmptyState";
import { PlatformShell } from "./app/PlatformShell";

type PlatformArea = "dashboard" | "investigations" | "entities" | "evidence" | "graph" | "tools" | "reports" | "timeline" | "settings";

export function App({ currentUser, onLogout }: { currentUser: User; onLogout: () => void }) {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [area, setArea] = useState<PlatformArea>("dashboard");
  const [cases, setCases] = useState<CaseRead[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [activeCase, setActiveCase] = useState<CaseRead | null>(null);
  const [sources, setSources] = useState<SourceRead[]>([]);
  const [graph, setGraph] = useState<GraphRead>({ nodes: [], edges: [] });
  const [graphAnalytics, setGraphAnalytics] = useState<GraphAnalytics | null>(null);
  const [custody, setCustody] = useState<CustodyReport | null>(null);
  const [monitor, setMonitor] = useState<CaseMonitor | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [targetPhotos, setTargetPhotos] = useState<TargetPhoto[]>([]);
  const [showNewCase, setShowNewCase] = useState(false);

  // Intake form state
  const [intake, setIntake] = useState({
    first_name: "", last_name: "", aliases: "", notes: "",
    legal_basis: "Authorized research", scope_statement: "Bounded authorized OSINT review using user-provided and public sources.",
    consent_basis: "User confirms authorization to investigate this target.", auto_search: true, photos: [] as File[],
  });

  const setSafeError = useCallback((message: string) => {
    setError(message);
    if (message) window.setTimeout(() => setError(""), 6000);
  }, []);

  const refreshCases = useCallback(async (caseId?: string) => {
    try {
      const allCases = await listCases();
      setCases(allCases);
      if (caseId) {
        const found = allCases.find((c) => c.id === caseId);
        if (found) {
          setActiveCaseId(found.id);
          setActiveCase(found);
          // Load case data
          const [src, g, anal, cust, mon, audit] = await Promise.all([
            listSources(found.id),
            getGraph(found.id),
            getGraphAnalytics(found.id).catch(() => null),
            getCustody(found.id).catch(() => null),
            getCaseMonitor(found.id).catch(() => null),
            listAuditEvents(found.id).catch(() => []),
          ]);
          setSources(src);
          setGraph(g);
          setGraphAnalytics(anal);
          setCustody(cust);
          setMonitor(mon);
          setAuditEvents(audit);
        }
      }
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Failed to load data");
    }
  }, [setSafeError]);

  useEffect(() => {
    refreshCases().catch(() => {});
  }, [refreshCases]);

  const refreshActiveCase = useCallback(async () => {
    if (activeCaseId) await refreshCases(activeCaseId);
  }, [activeCaseId, refreshCases]);

  const handleNavigate = useCallback((newArea: PlatformArea) => {
    setArea(newArea);
  }, []);

  const openCase = useCallback((caseId: string) => {
    setActiveCaseId(caseId);
    refreshCases(caseId).catch(() => {});
  }, [refreshCases]);

  const resetIntake = useCallback(() => {
    setIntake({ first_name: "", last_name: "", aliases: "", notes: "", legal_basis: "Authorized research", scope_statement: "", consent_basis: "User confirms authorization to investigate this target.", auto_search: true, photos: [] });
  }, []);

  const submitIntake = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await targetIntake(intake);
      setShowNewCase(false);
      resetIntake();
      setArea("investigations");
      openCase(result.case.id);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not create investigation");
    } finally {
      setLoading(false);
    }
  };

  const saveReport = async () => {
    if (!activeCaseId) return;
    try {
      const blob = await downloadReport(activeCaseId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${activeCase?.title?.replace(/[^a-z0-9_-]+/gi, "_") || "oihk-basic-report"}.md`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setSafeError(cause instanceof Error ? cause.message : "Could not download report");
    }
  };

  let content: React.ReactNode;

  switch (area) {
    case "dashboard":
      content = (
        <DashboardView
          cases={cases}
          activeCase={activeCase}
          graph={graph}
          selectedNode={null}
          onNavigate={handleNavigate}
          onNewCase={() => { resetIntake(); setShowNewCase(true); }}
        />
      );
      break;
    case "investigations":
      content = (
        <InvestigationsView
          cases={cases}
          activeCase={activeCase}
          onOpenCase={openCase}
          onNewCase={() => { resetIntake(); setShowNewCase(true); }}
          onOpenWorkspace={() => handleNavigate("graph")}
        />
      );
      break;
    case "entities":
      content = (
        <EntityManagerView
          nodes={graph.nodes}
          onRefresh={refreshActiveCase}
          onOpenGraph={() => handleNavigate("graph")}
          onError={setSafeError}
        />
      );
      break;
    case "evidence":
      content = (
        <EvidenceVaultView
          caseId={activeCaseId}
          sources={sources}
          photos={targetPhotos}
          custody={custody}
          onRefresh={refreshActiveCase}
        />
      );
      break;
    case "timeline":
      content = (
        <div className="platform-view">
          <WorkspaceHeader eyebrow="Chronological activity" title="Timeline" description="Audit events and collected sources in chronological order." />
          <TimelineView auditEvents={auditEvents} sources={sources} />
        </div>
      );
      break;
    case "graph":
      content = (
        <GraphWorkspaceView
          graph={graph}
          analytics={graphAnalytics}
          selectedNode={null}
          caseId={activeCaseId}
          onRefresh={refreshActiveCase}
          onOpenEntityManager={() => handleNavigate("entities")}
          onError={setSafeError}
        />
      );
      break;
    case "tools":
      content = (
        <ToolsWorkspaceView
          caseId={activeCaseId}
          isAdmin={currentUser.role === "admin" || currentUser.role === "system"}
          sources={sources}
          custody={custody}
          onRefresh={refreshActiveCase}
          onOpenEvidence={() => handleNavigate("evidence")}
        />
      );
      break;
    case "reports":
      content = activeCase ? (
        <ReportsWorkspaceView
          activeCase={activeCase}
          graph={graph}
          sources={sources}
          custody={custody}
          onDownloadMarkdown={() => void saveReport()}
        />
      ) : null;
      break;
    case "settings":
      content = (
        <SettingsView user={currentUser} />
      );
      break;
    default:
      content = null;
  }

  return (
    <>
      <PlatformShell
        area={area}
        cases={cases}
        activeCase={activeCase}
        currentUser={currentUser}
        loading={loading}
        error={error}
        onNavigate={handleNavigate}
        onOpenCase={openCase}
        onNewCase={() => { resetIntake(); setShowNewCase(true); }}
        onLogout={onLogout}
      >
        {content}
      </PlatformShell>
      <NewInvestigationDialog
        open={showNewCase}
        intake={intake}
        loading={loading}
        onChange={(patch) => setIntake({ ...intake, ...patch })}
        onClose={() => setShowNewCase(false)}
        onSubmit={submitIntake}
      />
    </>
  );
}
