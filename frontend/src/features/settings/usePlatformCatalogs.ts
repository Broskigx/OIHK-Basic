import { useCallback, useEffect, useState } from "react";
import { getProviderCatalog } from "../../api";
import type { ProviderCatalog } from "../../types";

export function usePlatformCatalogs() {
  const [providers, setProviders] = useState<ProviderCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setProviders(await getProviderCatalog());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Provider catalog could not be loaded.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { providers, loading, error, refresh };
}
