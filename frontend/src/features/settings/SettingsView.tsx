import React from "react";
import type { User } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";

export function SettingsView({ user }: { user: User }) {
  return (
    <div className="platform-view">
      <WorkspaceHeader eyebrow="Configuration" title="Settings" description="Application settings and user profile." />

      <div className="card" style={{ maxWidth: 600 }}>
        <h3 style={{ marginBottom: "1rem" }}>User Profile</h3>
        <table className="data-table">
          <tbody>
            <tr><td style={{ fontWeight: 600 }}>Username</td><td>{user.username}</td></tr>
            <tr><td style={{ fontWeight: 600 }}>Email</td><td>{user.email}</td></tr>
            <tr><td style={{ fontWeight: 600 }}>Role</td><td><span className="badge badge-info">{user.role}</span></td></tr>
            <tr><td style={{ fontWeight: 600 }}>Active</td><td><span className={`badge badge-${user.is_active ? "success" : "danger"}`}>{user.is_active ? "Yes" : "No"}</span></td></tr>
          </tbody>
        </table>
      </div>

      <div className="card" style={{ maxWidth: 600, marginTop: "1rem" }}>
        <h3 style={{ marginBottom: "1rem" }}>About OIHK Basic</h3>
        <table className="data-table">
          <tbody>
            <tr><td style={{ fontWeight: 600 }}>Version</td><td>0.1.0</td></tr>
            <tr><td style={{ fontWeight: 600 }}>Storage</td><td>Local SQLite</td></tr>
            <tr><td style={{ fontWeight: 600 }}>Data Location</td><td>./storage/ (configurable)</td></tr>
            <tr><td style={{ fontWeight: 600 }}>Auth</td><td>Local JWT</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
