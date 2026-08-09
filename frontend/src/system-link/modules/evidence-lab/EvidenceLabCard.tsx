import { ModulePowerCard } from "../../components/ModulePowerCard";
import type { ModulePowerAction } from "../../components/modulePowerModel";
import type { LinkedSystemModule } from "../../types";

function EvidenceLabBrand() {
  return <div className="evidence-lab-brand" aria-label="OIHK Evidence Lab"><span>OIHK</span><strong>EL</strong></div>;
}

export function EvidenceLabCard({
  module,
  busy,
  onAction,
}: {
  module: LinkedSystemModule;
  busy: boolean;
  onAction: (action: ModulePowerAction) => void;
}) {
  return <ModulePowerCard module={module} brand={<EvidenceLabBrand />} busy={busy} onAction={onAction} />;
}
