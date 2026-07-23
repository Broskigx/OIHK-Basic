import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="platform-empty" role="status">
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}
