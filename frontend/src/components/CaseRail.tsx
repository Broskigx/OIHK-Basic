import { ShieldCheck } from "lucide-react";
import type { CaseRead } from "../types";

export function CaseRail({
  cases,
  activeCaseId,
  onOpenCase,
}: {
  cases: CaseRead[];
  activeCaseId: string;
  onOpenCase: (caseId: string) => void;
}) {
  return (
    <aside className="rail">
      <div className="brand">
        <ShieldCheck size={26} />
        <div>
          <strong>OIHK</strong>
          <span>Open Intelligence</span>
        </div>
      </div>

      <div className="rail-block">
        <span className="rail-label">Casos</span>
        {cases.map((item) => (
          <button key={item.id} className={item.id === activeCaseId ? "case-row active" : "case-row"} onClick={() => onOpenCase(item.id)}>
            <span>{item.title}</span>
            <small>{item.status}</small>
          </button>
        ))}
      </div>
    </aside>
  );
}
