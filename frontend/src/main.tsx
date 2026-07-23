import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { setApiUrl } from "./api";
import type { User } from "./types";
import "./styles.css";
import "./app/platform.css";

// OIHK Basic — open-source local edition, auth disabled
const _SYSTEM_USER: User = {
  id: "system",
  email: "system@oihk-basic.local",
  username: "OIHK Basic",
  role: "admin",
  is_active: true,
  created_at: new Date().toISOString(),
};

export function Root() {
  const [ready, setReady] = useState(!("__TAURI_INTERNALS__" in window));
  const [startupError, setStartupError] = useState("");

  useEffect(() => {
    if (!("__TAURI_INTERNALS__" in window)) return;
    let cancelled = false;
    import("@tauri-apps/api/core")
      .then(({ invoke }) => invoke<{ port: number }>("get_backend_url"))
      .then(async ({ port }) => {
        const url = `http://127.0.0.1:${port}`;
        setApiUrl(url);
        for (let attempt = 0; attempt < 60; attempt += 1) {
          if (cancelled) return;
          try {
            const response = await fetch(`${url}/health`);
            if (response.ok) {
              setReady(true);
              return;
            }
          } catch {
            // The managed backend is still starting.
          }
          await new Promise((resolve) => window.setTimeout(resolve, 250));
        }
        throw new Error("The managed local service did not become ready within 15 seconds.");
      })
      .catch((cause) => {
        if (!cancelled) setStartupError(cause instanceof Error ? cause.message : "Could not start the local service");
      });
    return () => { cancelled = true; };
  }, []);

  if (startupError) return <main className="startup-state"><strong>OIHK Basic could not start</strong><p>{startupError}</p><button onClick={() => window.location.reload()}>Retry</button></main>;
  if (!ready) return <main className="startup-state"><strong>Starting OIHK Basic</strong><p>Preparing the private local workspace and SQLite service…</p></main>;
  return <App currentUser={_SYSTEM_USER} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
