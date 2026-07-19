import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { LoginView } from "./LoginView";
import { clearToken, hydrateToken, me } from "./api";
import type { User } from "./types";
import "./styles.css";

export function Root() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    hydrateToken()
      .then(() => me())
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setChecking(false));
  }, []);

  function logout() {
    void clearToken();
    setUser(null);
  }

  if (checking) {
    return <div className="boot-splash">Loading OIHK Basic…</div>;
  }
  if (!user) {
    return <LoginView onAuthed={setUser} />;
  }
  return <App currentUser={user} onLogout={logout} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
