import { useCallback, useEffect, useState } from "react";
import {
  isCaseScopedArea,
  parsePlatformHash,
  platformHash,
  type PlatformArea,
  type PlatformRoute,
} from "./navigation";

function currentRoute(): PlatformRoute {
  return parsePlatformHash(window.location.hash);
}

export function usePlatformRoute() {
  const [route, setRoute] = useState<PlatformRoute>(currentRoute);

  useEffect(() => {
    if (!window.location.hash) {
      window.history.replaceState(null, "", platformHash("dashboard"));
      setRoute(currentRoute());
    }
    const onHashChange = () => setRoute(currentRoute());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = useCallback((area: PlatformArea, caseId = "") => {
    window.location.hash = platformHash(area, caseId);
  }, []);

  const navigateCase = useCallback((caseId: string) => {
    const area = isCaseScopedArea(currentRoute().area) ? currentRoute().area : "investigations";
    window.location.hash = platformHash(area, caseId);
  }, []);

  return { route, navigate, navigateCase };
}
