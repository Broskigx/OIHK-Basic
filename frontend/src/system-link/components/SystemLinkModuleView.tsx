import { ShieldCheck } from "lucide-react";
import type { ModuleRouteId } from "../../app/navigation";
import { EmptyState } from "../../shared/ui/EmptyState";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type { LinkedSystemModule } from "../types";
import { ModuleSurface } from "./ModuleSurface";

export function SystemLinkModuleView({
  route,
  modules,
  activeCaseId,
}: {
  route: ModuleRouteId;
  modules: readonly LinkedSystemModule[];
  activeCaseId?: string;
}) {
  const [, moduleId, categoryId] = route.split(":");
  const module = modules.find((item) => item.module_id === moduleId);
  const category = module?.categories.find((item) => item.id === categoryId && item.enabled);
  if (!module || !category || !["READY", "BUSY"].includes(module.state)) {
    return (
      <div className="platform-view">
        <EmptyState
          title="Module route unavailable"
          description="This category is not registered by an authenticated READY System Link module."
        />
      </div>
    );
  }
  return (
    <div className="platform-view system-link-module-view">
      <WorkspaceHeader
        eyebrow={`${module.product_name} · isolated module surface`}
        title={category.label}
        description="The module bundle runs in a sandboxed, opaque-origin frame. It cannot touch Basic storage, tokens, or internals — data flows only through the allowlisted, versioned bridge."
        actions={
          <span className="platform-health good">
            <ShieldCheck size={14} /> {module.state}
          </span>
        }
      />
      <section className="platform-section">
        <ModuleSurface module={module} category={category} activeCaseId={activeCaseId} />
      </section>
    </div>
  );
}
