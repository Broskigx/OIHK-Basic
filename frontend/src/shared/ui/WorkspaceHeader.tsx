import React from "react";

export function WorkspaceHeader({
  eyebrow, title, description, children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="workspace-header">
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {children}
    </div>
  );
}
