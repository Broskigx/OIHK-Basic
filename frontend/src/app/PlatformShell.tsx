import {
  Activity,
  Bot,
  Boxes,
  BriefcaseBusiness,
  ChevronDown,
  CircleGauge,
  FileArchive,
  FileText,
  Database,
  Info,
  Network,
  Microscope,
  ScanSearch,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  HardDrive,
  AlertTriangle,
  Cpu,
  Cable,
  PackageCheck,
  Hexagon,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CaseRead, DesktopStatus, LocalModelRuntimeStatus, StorageStatus, User } from "../types";
import type { SystemLinkStatus } from "../system-link/types";
import { formatByteSize } from "../utils";
import { PRODUCT_VERSION } from "../version";
import {
  CORE_NAVIGATION,
  SIDEBAR_GROUPS,
  isModuleRouteId,
  type CorePlatformArea,
  type NavigationItem,
  type PlatformArea,
} from "./navigation";
import { CopilotDock } from "./CopilotDock";
import { useInterfaceMotion } from "./useInterfaceMotion";

const NAV_ICONS: Record<CorePlatformArea, LucideIcon> = {
  dashboard: CircleGauge,
  investigations: BriefcaseBusiness,
  entities: Boxes,
  evidence: FileArchive,
  timeline: Activity,
  graph: Network,
  osint: ScanSearch,
  tools: Microscope,
  reports: FileText,
  models: HardDrive,
  sources: Database,
  "system-link": Cable,
  settings: Settings,
  about: Info,
};

export function PlatformShell({
  area,
  cases,
  activeCase,
  currentUser,
  desktopStatus,
  storageStatus,
  localModelStatus,
  localModelLoading,
  activeCaseId,
  systemLinkStatus,
  moduleNavigation,
  loading,
  error,
  onNavigate,
  copilotOpen,
  copilotCollapsed,
  onCopilotOpenChange,
  onCopilotCollapsedChange,
  onOpenCase,
  onNewCase,
  onDismissError,
  onAgentDataChanged,
  children,
}: {
  area: PlatformArea;
  cases: CaseRead[];
  activeCase?: CaseRead;
  currentUser: User;
  desktopStatus: DesktopStatus | null;
  storageStatus: StorageStatus | null;
  localModelStatus: LocalModelRuntimeStatus | null;
  localModelLoading: boolean;
  activeCaseId: string | null;
  systemLinkStatus: SystemLinkStatus | null;
  moduleNavigation: readonly NavigationItem[];
  loading: boolean;
  error: string;
  onNavigate: (area: PlatformArea) => void;
  copilotOpen: boolean;
  copilotCollapsed: boolean;
  onCopilotOpenChange: (open: boolean) => void;
  onCopilotCollapsedChange: (collapsed: boolean) => void;
  onOpenCase: (caseId: string) => void;
  onNewCase: () => void;
  onDismissError: () => void;
  onAgentDataChanged: () => void;
  children: React.ReactNode;
}) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem("oihk.sidebar.collapsed") === "true");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const shellRef = useRef<HTMLElement>(null);

  useInterfaceMotion(area, shellRef);

  useEffect(() => {
    window.localStorage.setItem("oihk.sidebar.collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  // Global search shortcut: Ctrl+K
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(true);
        setTimeout(() => searchRef.current?.focus(), 50);
      }
      if (e.key === "Escape") {
        setSearchOpen(false);
        setSearchQuery("");
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const handleSearchInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  }, []);

  const handleSearchKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setSearchOpen(false);
      setSearchQuery("");
    }
  }, []);

  const appVersion = desktopStatus?.version ?? PRODUCT_VERSION;
  const searchResults = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase();
    if (!query) return [];
    return cases
      .filter((item) =>
        [item.title, item.summary, item.scope_statement]
          .filter(Boolean)
          .some((value) => value!.toLocaleLowerCase().includes(query)),
      )
      .slice(0, 6);
  }, [cases, searchQuery]);

  const navByGroup = useMemo(() => {
    const groups = new Map<string, NavigationItem[]>();
    for (const item of [...CORE_NAVIGATION, ...moduleNavigation]) {
      if (item.sidebar === false) continue;
      const g = item.group || "workspace";
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g)!.push(item);
    }
    return groups;
  }, [moduleNavigation]);

  const storageLabel = storageStatus
    ? `${formatByteSize(storageStatus.database_bytes + storageStatus.evidence_bytes)} · ${storageStatus.writable ? "Writable" : "Read-only"}`
    : "Checking local storage…";

  const connectedModules = systemLinkStatus?.modules.filter(
    (module) => module.enabled && (module.state === "READY" || module.state === "BUSY"),
  ).length ?? 0;
  const modelLabel = localModelLoading
    ? "Checking model…"
    : localModelStatus?.connected
      ? `${localModelStatus.model || localModelStatus.provider} ready`
      : localModelStatus?.error === "StatusUnavailable"
        ? "Model status unavailable"
      : localModelStatus?.configured
        ? "Model offline"
        : "Model not configured";

  return (
    <main ref={shellRef} data-area={area} className={`platform-shell${sidebarCollapsed ? " sidebar-collapsed" : ""}${copilotOpen ? " copilot-open" : ""}${copilotCollapsed ? " copilot-collapsed" : ""}`}>
      {/* ── Sidebar ── */}
      <aside className={mobileSidebarOpen ? "platform-sidebar mobile-open" : "platform-sidebar"}>
        {/* Brand */}
        <div className="platform-brand">
          <span className="platform-brand-mark"><Hexagon size={27} /><i /></span>
          <div className="platform-brand-info">
            <strong>OIHK Basic</strong>
            <small>Local Intelligence Workspace</small>
          </div>
          <button type="button" className="platform-sidebar-toggle" onClick={() => setSidebarCollapsed((value) => !value)} aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {sidebarCollapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          </button>
        </div>

        {/* Navigation groups */}
        <nav className="platform-nav" aria-label="Main navigation">
          {SIDEBAR_GROUPS.map((group) => {
            const items = navByGroup.get(group.id);
            if (!items || items.length === 0) return null;
            return (
              <div key={group.id} className="platform-nav-group">
                <span className="platform-nav-group-label">{group.label}</span>
                {items.map((item) => {
                  const Icon = isModuleRouteId(item.id) ? PackageCheck : NAV_ICONS[item.id];
                  return (
                    <button
                      type="button"
                      key={item.id}
                      className={area === item.id ? "platform-nav-item active" : "platform-nav-item"}
                      onClick={() => { onNavigate(item.id); setMobileSidebarOpen(false); }}
                      title={item.label}
                      aria-current={area === item.id ? "page" : undefined}
                    >
                      <Icon size={16} aria-hidden="true" />
                      <span>{item.label}</span>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* Sidebar footer */}
        <div className="platform-sidebar-footer">
          <div className="platform-storage-status">
            <HardDrive size={12} />
            <div className="platform-storage-info">
              <span className="platform-storage-label">Local Storage</span>
              <span className="platform-storage-text">{storageLabel}</span>
            </div>
          </div>
          <div className="platform-sidebar-bottom">
            <div className="platform-sidebar-brand-bottom">
              <span className="platform-brand-mark-sm"><Hexagon size={15} /></span>
              <span className="platform-version">
                OIHK Basic v{appVersion}
              </span>
            </div>
            <span className="platform-runtime-badge">
              {desktopStatus ? "Desktop" : "Web"}
            </span>
          </div>
          <div className="platform-sidebar-local-badge">
            <ShieldCheck size={10} />
            <span>Local-First</span>
          </div>
        </div>
      </aside>

      {/* ── Topbar ── */}
      <header className="platform-topbar">
        <div className="platform-topbar-left">
          <button type="button" className="platform-mobile-menu" onClick={() => setMobileSidebarOpen((value) => !value)} aria-label="Toggle navigation"><Menu size={17} /></button>
          {/* Case selector */}
          <div className="platform-case-context">
            <span className="platform-context-label">Case</span>
            <label className="platform-case-select">
              <ShieldCheck size={14} color="var(--accent)" />
              <select
                aria-label="Active investigation"
                value={activeCase?.id ?? ""}
                onChange={(event) => onOpenCase(event.target.value)}
                disabled={cases.length === 0 || loading}
              >
                {cases.length === 0 && <option value="">No investigations</option>}
                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </select>
              <ChevronDown size={12} />
            </label>
            {activeCase && (
              <span className={`placo-badge ${activeCase.status}`}>{activeCase.status}</span>
            )}
          </div>

          {/* Global search */}
          <div className="platform-search">
            <Search size={14} color="var(--text-muted)" />
            <input
              ref={searchRef}
              type="text"
              placeholder="Search investigations"
              value={searchQuery}
              onChange={handleSearchInput}
              onKeyDown={handleSearchKeyDown}
              onFocus={() => setSearchOpen(true)}
              onBlur={() => setTimeout(() => setSearchOpen(false), 200)}
              aria-label="Global search"
            />
            <span className="platform-search-shortcut">Ctrl+K</span>
            {searchOpen && searchQuery.trim() && (
              <div className="platform-search-results" role="listbox" aria-label="Search results">
                {searchResults.length === 0 ? (
                  <span className="platform-search-empty">No matching investigations</span>
                ) : (
                  searchResults.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      role="option"
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => {
                        onOpenCase(item.id);
                        setSearchOpen(false);
                        setSearchQuery("");
                      }}
                    >
                      <strong>{item.title}</strong>
                      <span>{item.status}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        <div className="platform-topbar-right">
          {/* Model status indicator */}
          <div className={`platform-model-status ${localModelStatus?.connected ? "connected" : "offline"}`} title={modelLabel}>
            <Cpu size={13} />
            <span>{modelLabel}</span>
          </div>

          <div className={`platform-runtime-status ${storageStatus ? "connected" : "checking"}`} title="Local SQLite status">
            <Database size={13} /><span>{storageStatus ? "SQLite ready" : "Checking SQLite…"}</span>
          </div>

          <div className={`platform-runtime-status ${connectedModules > 0 ? "connected" : "idle"}`} title="System Link modules in READY or BUSY state">
            <Cable size={13} /><span>{connectedModules} linked</span>
          </div>

          <span className="platform-topbar-badge">Local mode</span>

          {/* New Investigation button */}
          <button type="button" className="platform-ghost-btn" onClick={onNewCase} disabled={loading}>
            <Plus size={14} />
            New Investigation
          </button>

          {/* Settings button */}
          <button
            type="button"
            className="platform-icon-btn"
            onClick={() => onNavigate("settings")}
            title="Settings"
          >
            <Settings size={15} />
          </button>

          {!copilotOpen && <button type="button" className="platform-icon-btn" onClick={() => { onCopilotOpenChange(true); onCopilotCollapsedChange(false); }} title="Open Copilot" aria-label="Open Copilot"><Bot size={15} /></button>}

          {/* User chip */}
          <div className="platform-user-chip">
            <span className="platform-user-avatar">
              {currentUser.username.slice(0, 1).toUpperCase()}
            </span>
            <div className="platform-user-info">
              <strong>{currentUser.username}</strong>
              <small>{currentUser.role}</small>
            </div>
          </div>
        </div>
      </header>

      {/* ── Content ── */}
      <section className="platform-main" aria-live="polite">
        {error && (
          <div className="platform-error" role="alert">
            <div className="platform-error-content">
              <AlertTriangle size={14} />
              <span className="platform-error-text">{error}</span>
              <button
                type="button"
                className="platform-error-dismiss"
                onClick={onDismissError}
                aria-label="Dismiss error"
              >
                &times;
              </button>
            </div>
          </div>
        )}
        {children}
      </section>
      <CopilotDock
        open={copilotOpen}
        collapsed={copilotCollapsed}
        modelStatus={localModelStatus}
        caseId={activeCaseId}
        onOpen={() => { onCopilotOpenChange(true); onCopilotCollapsedChange(false); }}
        onClose={() => onCopilotOpenChange(false)}
        onToggleCollapsed={() => onCopilotCollapsedChange(!copilotCollapsed)}
        onOpenModels={() => onNavigate("models")}
        onDataChanged={onAgentDataChanged}
      />
    </main>
  );
}
