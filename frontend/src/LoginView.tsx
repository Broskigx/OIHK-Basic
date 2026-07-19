import React, { useState } from "react";
import { login, register, setToken } from "./api";
import type { User } from "./types";

export function LoginView({ onAuthed }: { onAuthed: (user: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const payload = mode === "login"
        ? await login({ email, password })
        : await register({ email, username, password });
      await setToken(payload.access_token);
      onAuthed(payload.user);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>OIHK Basic</h1>
        <p className="subtitle">Local-first investigation platform</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@example.com"
              required
            />
          </div>

          {mode === "register" && (
            <div className="form-group">
              <label>Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                required
              />
            </div>
          )}

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              minLength={8}
            />
          </div>

          {error && <div className="error-banner" style={{ marginBottom: "1rem" }}>{error}</div>}

          <button type="submit" className="primary" style={{ width: "100%" }} disabled={loading}>
            {loading ? "Processing…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p style={{ textAlign: "center", marginTop: "1rem", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          {mode === "login" ? (
            <>No account?{" "}<a href="#" onClick={(e) => { e.preventDefault(); setMode("register"); setError(""); }} style={{ color: "var(--accent)" }}>Register</a></>
          ) : (
            <>Already have an account?{" "}<a href="#" onClick={(e) => { e.preventDefault(); setMode("login"); setError(""); }} style={{ color: "var(--accent)" }}>Sign in</a></>
          )}
        </p>
      </div>
    </div>
  );
}
