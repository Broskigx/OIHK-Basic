import { Download, Fingerprint, LogOut, RefreshCw, ShieldCheck, SlidersHorizontal, Sparkles, Zap } from "lucide-react";
import type { AppMode, CaseRead, CustodyReport, DesktopStatus, TargetProfile, User } from "../types";

export function AppHeader({
  appMode,
  onModeChange,
  isAnalysisView,
  activeCase,
  activeTarget,
  activeCaseId,
  desktopStatus,
  custody,
  currentUser,
  loading,
  onNewSearch,
  onRefresh,
  onSaveReport,
  onLogout,
}: {
  appMode: AppMode;
  onModeChange: (mode: AppMode) => void;
  isAnalysisView: boolean;
  activeCase?: CaseRead;
  activeTarget?: TargetProfile;
  activeCaseId: string;
  desktopStatus: DesktopStatus | null;
  custody: CustodyReport | null;
  currentUser: User;
  loading: boolean;
  onNewSearch: () => void;
  onRefresh: () => void;
  onSaveReport: () => void;
  onLogout: () => void;
}) {
  return (
    <header className="command">
      <div>
        <span className="eyebrow">
          <Fingerprint size={14} />
          Authorized intelligence workspace
        </span>
        <h1>{isAnalysisView && activeTarget ? `${activeTarget.first_name} ${activeTarget.last_name}` : "Nueva busqueda OIHK"}</h1>
        <p>{isAnalysisView ? activeCase?.legal_basis ?? "Caso preparado" : "Entrada preliminar"}</p>
        <div className="runtime-badge">
          <span>{desktopStatus ? "Desktop Pro" : "Web workspace"}</span>
          <small>{desktopStatus ? `${desktopStatus.platform} / v${desktopStatus.version}` : "127.0.0.1 conectado"}</small>
        </div>
      </div>
      <div className="actions">
        <div className="mode-switch" role="tablist" aria-label="Modo OIHK">
          <button
            type="button"
            className={appMode === "ai" ? "mode-pill active" : "mode-pill"}
            onClick={() => onModeChange("ai")}
            disabled={loading}
          >
            <Zap size={14} />
            OIHK AI
          </button>
          <button
            type="button"
            className={appMode === "pro" ? "mode-pill active" : "mode-pill"}
            onClick={() => onModeChange("pro")}
            disabled={loading}
          >
            <SlidersHorizontal size={14} />
            Professional
          </button>
        </div>
        {isAnalysisView && (
          <button onClick={onNewSearch} disabled={loading}>
            <Sparkles size={16} />
            Nueva
          </button>
        )}
        <button onClick={onRefresh} disabled={loading}>
          <RefreshCw size={16} />
          Refrescar
        </button>
        {isAnalysisView && activeCaseId && (
          <button type="button" onClick={onSaveReport}>
            <Download size={16} />
            Reporte
          </button>
        )}
        {isAnalysisView && custody && custody.sealed_count > 0 && (
          <div
            className={custody.intact ? "custody-pill intact" : "custody-pill broken"}
            title={`Cadena de custodia · ${custody.sealed_count} sellos SHA-256 encadenados`}
          >
            <ShieldCheck size={14} />
            {custody.intact
              ? `Custodia íntegra · ${custody.sealed_count}`
              : `Custodia alterada (#${custody.first_broken_sequence})`}
          </div>
        )}
        <div className="user-chip" title={currentUser.email}>
          <span>{currentUser.username}</span>
          <small>{currentUser.role}</small>
        </div>
        <button className="ghost" onClick={onLogout} title="Cerrar sesión">
          <LogOut size={16} />
        </button>
      </div>
    </header>
  );
}
