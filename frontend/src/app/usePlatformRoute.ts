import { useCallback, useEffect, useState } from "react";
import {
  isCaseScopedArea,
  parsePlatformHash,
  platformHash,
  type PlatformArea,
  type PlatformRoute,
  type NavigationItem,
} from "./navigation";

function currentRoute(moduleNavigation: readonly NavigationItem[]): PlatformRoute {
  return parsePlatformHash(window.location.hash, moduleNavigation);
}

export function usePlatformRoute(moduleNavigation: readonly NavigationItem[] = []) {
  const [route, setRoute] = useState<PlatformRoute>(() => currentRoute(moduleNavigation));

  useEffect(() => {
    if (!window.location.hash) {
      window.history.replaceState(null, "", platformHash("dashboard"));
      setRoute(currentRoute(moduleNavigation));
    }
    const onHashChange = () => setRoute(currentRoute(moduleNavigation));
    window.addEventListener("hashchange", onHashChange);
    setRoute(currentRoute(moduleNavigation));
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [moduleNavigation]);

  const navigate = useCallback((area: PlatformArea, caseId = "") => {
    window.location.hash = platformHash(area, caseId);
  }, []);

  const navigateCase = useCallback((caseId: string) => {
    const current = currentRoute(moduleNavigation);
    const area = isCaseScopedArea(current.area, moduleNavigation) ? current.area : "investigations";
    window.location.hash = platformHash(area, caseId);
  }, [moduleNavigation]);

  return { route, navigate, navigateCase };
}
