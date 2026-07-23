import type { ReactNode } from "react";

export function WorkspaceHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="platform-workspace-header">
      <div>
        {eyebrow && <span className="platform-eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="platform-header-actions">{actions}</div>}
    </header>
  );
}
