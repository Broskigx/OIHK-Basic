export type CorePlatformArea =
  | "dashboard"
  | "investigations"
  | "entities"
  | "evidence"
  | "timeline"
  | "graph"
  | "osint"
  | "tools"
  | "reports"
  | "models"
  | "sources"
  | "system-link"
  | "settings"
  | "about";

export type ModuleRouteId = `module:${string}:${string}`;
export type PlatformArea = CorePlatformArea | ModuleRouteId;

export type PlatformRoute = {
  area: PlatformArea;
  caseId: string;
};

export type NavigationItem = {
  id: PlatformArea;
  label: string;
  caseScoped: boolean;
  sidebar?: boolean;
  group?: string;
  icon?: string;
  moduleId?: string;
  order?: number;
};

export const SIDEBAR_GROUPS: { id: string; label: string }[] = [
  { id: "primary", label: "Workspace" },
  { id: "linked-modules", label: "Linked modules" },
  { id: "more", label: "More tools" },
];

export const CORE_NAVIGATION: NavigationItem[] = [
  { id: "dashboard", label: "Dashboard", caseScoped: false, group: "primary" },
  { id: "investigations", label: "Investigations", caseScoped: false, group: "primary" },
  { id: "graph", label: "Graph", caseScoped: true, group: "primary" },
  { id: "evidence", label: "Evidence", caseScoped: true, group: "primary" },
  { id: "reports", label: "Reports", caseScoped: true, group: "primary" },
  { id: "models", label: "Local Models", caseScoped: false, group: "primary" },
  { id: "system-link", label: "System Link", caseScoped: false, group: "primary" },
  { id: "settings", label: "Settings", caseScoped: false, group: "primary" },
  { id: "entities", label: "Entities", caseScoped: true, group: "more" },
  { id: "timeline", label: "Timeline", caseScoped: true, group: "more" },
  { id: "osint", label: "OSINT Workspace", caseScoped: true, group: "more" },
  { id: "tools", label: "Tools", caseScoped: true, group: "more" },
  { id: "sources", label: "Data Sources", caseScoped: true, group: "more" },
  { id: "about", label: "About", caseScoped: false, group: "more" },
];

// Compatibility export for callers/tests that still use the original catalog name.
export const MAIN_NAVIGATION = CORE_NAVIGATION;

const CORE_IDS = new Set(CORE_NAVIGATION.map((item) => item.id));
const GLOBAL_AREAS = new Set<CorePlatformArea>([
  "dashboard",
  "investigations",
  "models",
  "system-link",
  "settings",
  "about",
]);
const MODULE_ROUTE_RE = /^module:([a-z0-9](?:[a-z0-9.-]{1,78}[a-z0-9])?):([a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)$/;

export function isModuleRouteId(value: string): value is ModuleRouteId {
  return MODULE_ROUTE_RE.test(value);
}

export function createModuleRouteId(moduleId: string, categoryId: string): ModuleRouteId {
  const value = `module:${moduleId}:${categoryId}`;
  if (!isModuleRouteId(value)) throw new Error("Invalid namespaced System Link module route");
  return value;
}

export function isCaseScopedArea(area: PlatformArea, moduleNavigation: readonly NavigationItem[] = []): boolean {
  if (isModuleRouteId(area)) return moduleNavigation.some((item) => item.id === area && item.caseScoped);
  return CORE_NAVIGATION.some((item) => item.id === area && item.caseScoped);
}

function registeredModuleRoute(
  moduleId: string,
  categoryId: string,
  moduleNavigation: readonly NavigationItem[],
): ModuleRouteId | null {
  try {
    const route = createModuleRouteId(moduleId, categoryId);
    return moduleNavigation.some((item) => item.id === route) ? route : null;
  } catch {
    return null;
  }
}

export function parsePlatformHash(
  hash: string,
  moduleNavigation: readonly NavigationItem[] = [],
): PlatformRoute {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "modules") {
    const route = registeredModuleRoute(decodeURIComponent(parts[1] ?? ""), decodeURIComponent(parts[2] ?? ""), moduleNavigation);
    return route ? { area: route, caseId: "" } : { area: "dashboard", caseId: "" };
  }
  if (parts[0] !== "investigations") {
    if (GLOBAL_AREAS.has(parts[0] as CorePlatformArea)) return { area: parts[0] as CorePlatformArea, caseId: "" };
    return { area: "dashboard", caseId: "" };
  }
  if (parts.length === 1) return { area: "investigations", caseId: "" };

  const caseId = decodeURIComponent(parts[1] ?? "");
  if (parts[2] === "modules") {
    const route = registeredModuleRoute(
      decodeURIComponent(parts[3] ?? ""),
      decodeURIComponent(parts[4] ?? ""),
      moduleNavigation,
    );
    return route && isCaseScopedArea(route, moduleNavigation)
      ? { area: route, caseId }
      : { area: "investigations", caseId };
  }
  const requested = parts[2] === "overview" ? "investigations" : parts[2];
  const area = CORE_IDS.has(requested as CorePlatformArea)
    ? (requested as CorePlatformArea)
    : "investigations";
  return { area, caseId };
}

export function platformHash(area: PlatformArea, caseId = ""): string {
  if (isModuleRouteId(area)) {
    const [, moduleId, categoryId] = area.split(":");
    if (caseId) {
      return `#/investigations/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}/${encodeURIComponent(categoryId)}`;
    }
    return `#/modules/${encodeURIComponent(moduleId)}/${encodeURIComponent(categoryId)}`;
  }
  if (GLOBAL_AREAS.has(area) && area !== "investigations") return `#/${area}`;
  if (area === "investigations" && !caseId) return "#/investigations";
  if (!caseId) return "#/investigations";
  const section = area === "investigations" ? "overview" : area;
  return `#/investigations/${encodeURIComponent(caseId)}/${section}`;
}
