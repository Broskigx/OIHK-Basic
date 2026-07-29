import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { getApiUrl, me, setApiUrl } from "./api";
import { LoginView } from "./LoginView";
import type { User } from "./types";
import "./styles.css";
import "./app/platform.css";

export function Root() {
  const [ready, setReady] = useState(false);
  const [startupError, setStartupError] = useState("");
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [requiresLogin, setRequiresLogin] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        let url = getApiUrl();
        if ("__TAURI_INTERNALS__" in window) {
          const { invoke } = await import("@tauri-apps/api/core");
          const { port } = await invoke<{ port: number }>("get_backend_url");
          url = `http://127.0.0.1:${port}`;
          setApiUrl(url);
        }

        let healthy = false;
        for (let attempt = 0; attempt < 60; attempt += 1) {
          if (cancelled) return;
          try {
            const response = await fetch(`${url}/health`);
            if (response.ok) {
              healthy = true;
              break;
            }
          } catch {
            // The managed backend is still starting.
          }
          await new Promise((resolve) => window.setTimeout(resolve, 250));
        }
        if (!healthy) {
          throw new Error("The managed local service did not become ready within 15 seconds.");
        }

        try {
          const user = await me();
          if (!cancelled) setCurrentUser(user);
        } catch (cause) {
          const message = cause instanceof Error ? cause.message : "";
          if (message.includes("Session expired") || message.includes("Authentication required")) {
            if (!cancelled) setRequiresLogin(true);
          } else {
            throw cause;
          }
        }
      } catch (cause) {
        if (!cancelled) {
          setStartupError(cause instanceof Error ? cause.message : "Could not start the local service");
        }
      } finally {
        if (!cancelled) setReady(true);
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  if (startupError) {
    return (
      <main className="startup-state">
        <strong>OIHK Basic could not start</strong>
        <p>{startupError}</p>
        <button type="button" onClick={() => window.location.reload()}>Retry</button>
      </main>
    );
  }
  if (!ready) {
    return (
      <main className="startup-state">
        <strong>Starting OIHK Basic</strong>
        <p>Preparing the private local workspace and SQLite service…</p>
      </main>
    );
  }
  if (requiresLogin || !currentUser) {
    return (
      <LoginView
        onAuthed={(user) => {
          setCurrentUser(user);
          setRequiresLogin(false);
        }}
      />
    );
  }
  return <App currentUser={currentUser} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
