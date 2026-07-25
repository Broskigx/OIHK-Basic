export type PlatformArea =
  | "dashboard"
  | "investigations"
  | "entities"
  | "evidence"
  | "timeline"
  | "graph"
  | "osint"
  | "tools"
  | "reports"
  | "copilot"
  | "models"
  | "sources"
  | "settings"
  | "about";

export type PlatformRoute = {
  area: PlatformArea;
  caseId: string;
};

export type NavigationItem = {
  id: PlatformArea;
  label: string;
  caseScoped: boolean;
  sidebar?: boolean;
};

export const MAIN_NAVIGATION: NavigationItem[] = [
  { id: "dashboard", label: "Dashboard", caseScoped: false },
  { id: "investigations", label: "Investigations", caseScoped: false },
  { id: "graph", label: "Intelligence Graph", caseScoped: true },
  { id: "osint", label: "OSINT Workspace", caseScoped: true },
  { id: "evidence", label: "Evidence Lab", caseScoped: true },
  { id: "reports", label: "Reports", caseScoped: true },
  { id: "copilot", label: "Copilot", caseScoped: true },
  { id: "models", label: "Local Models", caseScoped: false },
  { id: "sources", label: "Data Sources", caseScoped: true },
  { id: "settings", label: "Settings", caseScoped: false },
  { id: "about", label: "About", caseScoped: false },
  { id: "entities", label: "Entities", caseScoped: true, sidebar: false },
  { id: "timeline", label: "Timeline", caseScoped: true, sidebar: false },
  { id: "tools", label: "Forensics", caseScoped: true, sidebar: false },
];

const GLOBAL_AREAS = new Set<PlatformArea>(["dashboard", "investigations", "models", "settings", "about"]);

const CASE_AREAS = new Set<PlatformArea>(
  MAIN_NAVIGATION.filter((item) => item.caseScoped).map((item) => item.id),
);

export function isCaseScopedArea(area: PlatformArea): boolean {
  return CASE_AREAS.has(area);
}

export function parsePlatformHash(hash: string): PlatformRoute {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] !== "investigations") {
    if (GLOBAL_AREAS.has(parts[0] as PlatformArea)) return { area: parts[0] as PlatformArea, caseId: "" };
    return { area: "dashboard", caseId: "" };
  }
  if (parts.length === 1) return { area: "investigations", caseId: "" };

  const caseId = decodeURIComponent(parts[1] ?? "");
  const requested = parts[2] === "overview" ? "investigations" : parts[2];
  const area = MAIN_NAVIGATION.some((item) => item.id === requested)
    ? (requested as PlatformArea)
    : "investigations";
  return { area, caseId };
}

export function platformHash(area: PlatformArea, caseId = ""): string {
  if (GLOBAL_AREAS.has(area) && area !== "investigations") return `#/${area}`;
  if (area === "investigations" && !caseId) return "#/investigations";
  if (!caseId) return "#/investigations";
  const section = area === "investigations" ? "overview" : area;
  return `#/investigations/${encodeURIComponent(caseId)}/${section}`;
}
