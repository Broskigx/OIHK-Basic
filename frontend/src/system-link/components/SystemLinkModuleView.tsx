import { Boxes, ShieldCheck } from "lucide-react";
import type { ModuleRouteId } from "../../app/navigation";
import { EmptyState } from "../../shared/ui/EmptyState";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type { LinkedSystemModule } from "../types";

export function SystemLinkModuleView({ route, modules }: { route: ModuleRouteId; modules: readonly LinkedSystemModule[] }) {
  const [, moduleId, categoryId] = route.split(":");
  const module = modules.find((item) => item.module_id === moduleId);
  const category = module?.categories.find((item) => item.id === categoryId && item.enabled);
  if (!module || !category || !["READY", "BUSY"].includes(module.state)) {
    return <div className="platform-view"><EmptyState title="Module route unavailable" description="This category is not registered by an authenticated READY System Link module." /></div>;
  }
  return (
    <div className="platform-view system-link-module-surface">
      <WorkspaceHeader
        eyebrow={`${module.product_name} · signed module category`}
        title={category.label}
        description="The route is namespaced and activated only while its separately installed runtime is authenticated and healthy."
        actions={<span className="platform-health good"><ShieldCheck size={14} /> {module.state}</span>}
      />
      <section className="platform-section">
        <div className="platform-section-heading"><div><span className="platform-eyebrow">Controlled module boundary</span><h2>System Link module surface</h2></div><Boxes size={18} /></div>
        <p>This host surface exposes only the route and capabilities declared by the verified manifest. Evidence Lab domain processing remains in the separate runtime.</p>
        <dl className="platform-property-list"><div><dt>Module</dt><dd>{module.module_id}</dd></div><div><dt>Category</dt><dd>{category.id}</dd></div><div><dt>Granted capabilities</dt><dd>{module.granted_capabilities.join(", ") || "None"}</dd></div><div><dt>Last health</dt><dd>{module.last_health_at ? new Date(module.last_health_at).toLocaleString() : "Not recorded"}</dd></div></dl>
      </section>
    </div>
  );
}
