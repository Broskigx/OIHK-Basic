import React from "react";
import type { CaseRead, User } from "../types";

type PlatformArea = "dashboard" | "investigations" | "entities" | "evidence" | "graph" | "tools" | "reports" | "timeline" | "settings";

const NAV_ITEMS: { id: PlatformArea; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "investigations", label: "Investigations" },
  { id: "graph", label: "Graph" },
  { id: "entities", label: "Entities" },
  { id: "evidence", label: "Evidence" },
  { id: "tools", label: "Tools" },
  { id: "reports", label: "Reports" },
  { id: "timeline", label: "Timeline" },
  { id: "settings", label: "Settings" },
];

export function PlatformShell({
  area, cases, activeCase, currentUser, loading, error, children,
  onNavigate, onOpenCase, onNewCase, onLogout,
}: {
  area: PlatformArea;
  cases: CaseRead[];
  activeCase: CaseRead | undefined;
  currentUser: User;
  loading: boolean;
  error: string;
  children: React.ReactNode;
  onNavigate: (area: PlatformArea) => void;
  onOpenCase: (id: string) => void;
  onNewCase: () => void;
  onLogout: () => void;
}) {
  return (
    <div className="platform-shell">
      <header className="platform-header">
        <div className="header-brand">
          <span style={{ color: "var(--accent)" }}>◆</span>
          OIHK Basic
        </div>

        <nav className="header-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`nav-btn ${area === item.id ? "active" : ""}`}
              onClick={() => onNavigate(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="header-user">
          {activeCase && (
            <span title={activeCase.title} style={{ maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {activeCase.title}
            </span>
          )}
          <button className="nav-btn" onClick={onNewCase}>+ New</button>
          <span>{currentUser.username}</span>
          <button className="nav-btn" onClick={onLogout}>Logout</button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div className="platform-body">
        {children}
      </div>
    </div>
  );
}
