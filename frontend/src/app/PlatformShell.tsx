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
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CaseRead, DesktopStatus, User } from "../types";
import { PRODUCT_VERSION } from "../version";
import { MAIN_NAVIGATION, type PlatformArea } from "./navigation";

const NAV_ICONS: Record<PlatformArea, LucideIcon> = {
  dashboard: CircleGauge,
  investigations: BriefcaseBusiness,
  entities: Boxes,
  evidence: FileArchive,
  timeline: Activity,
  graph: Network,
  osint: ScanSearch,
  tools: Microscope,
  reports: FileText,
  copilot: Bot,
  models: HardDrive,
  sources: Database,
  settings: Settings,
  about: Info,
};

export function PlatformShell({
  area,
  cases,
  activeCase,
  currentUser,
  desktopStatus,
  loading,
  error,
  onNavigate,
  onOpenCase,
  onNewCase,
  onDismissError,
  children,
}: {
  area: PlatformArea;
  cases: CaseRead[];
  activeCase?: CaseRead;
  currentUser: User;
  desktopStatus: DesktopStatus | null;
  loading: boolean;
  error: string;
  onNavigate: (area: PlatformArea) => void;
  onOpenCase: (caseId: string) => void;
  onNewCase: () => void;
  onDismissError: () => void;
  children: React.ReactNode;
}) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

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

  return (
    <main className="platform-shell">
      {/* ── Sidebar ── */}
      <aside className="platform-sidebar">
        <div className="platform-brand">
          <span className="platform-brand-mark">O</span>
          <div className="platform-brand-info">
            <strong>OIHK Basic</strong>
            <small>Local-First OSINT</small>
          </div>
        </div>

        <nav className="platform-nav" aria-label="Main navigation">
          {MAIN_NAVIGATION.filter((item) => item.sidebar !== false).map((item) => {
            const Icon = NAV_ICONS[item.id];
            return (
              <button
                type="button"
                key={item.id}
                className={area === item.id ? "platform-nav-item active" : "platform-nav-item"}
                onClick={() => onNavigate(item.id)}
                title={item.label}
              >
                <Icon size={16} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="platform-sidebar-footer">
          <div className="platform-storage-status">
            <HardDrive size={12} />
            <div className="platform-storage-info">
              <span className="platform-storage-label">Local Storage</span>
              <div className="platform-storage-bar">
                <i style={{ width: "34%" }} />
              </div>
              <span className="platform-storage-text">Local data saved</span>
            </div>
          </div>
          <div className="platform-sidebar-bottom">
            <div className="platform-sidebar-brand-bottom">
              <span className="platform-brand-mark-sm">O</span>
              <span className="platform-version">
                OIHK Basic v{appVersion}
              </span>
            </div>
            <span className="platform-runtime-badge">
              {desktopStatus ? "Desktop" : "Web"}
            </span>
          </div>
        </div>
      </aside>

      {/* ── Topbar ── */}
      <header className="platform-topbar">
        <div className="platform-topbar-left">
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
          </div>

          <div className="platform-search">
            <Search size={14} color="var(--text-muted)" />
            <input
              ref={searchRef}
              type="text"
              placeholder="Search investigations..."
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
          <span className="platform-topbar-badge">Local-First</span>
          {activeCase && (
            <span className="platform-topbar-badge" style={{ opacity: 0.7 }}>
              {activeCase.status}
            </span>
          )}
          <button type="button" className="platform-ghost-btn" onClick={onNewCase} disabled={loading}>
            <Plus size={14} />
            New Case
          </button>
          <button
            type="button"
            className="platform-icon-btn"
            onClick={() => onNavigate("settings")}
            title="Settings"
          >
            <Settings size={15} />
          </button>
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
      <section className="platform-main">
        {error && (
          <div className="platform-error" role="alert">
            <div className="platform-error-content">
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
    </main>
  );
}
