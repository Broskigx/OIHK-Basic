import type { ModuleLifecycleAction, SystemLinkModuleState } from "../types";

export type ModulePowerAction = ModuleLifecycleAction | "pair" | "open";

export function moduleActionsForState(state: SystemLinkModuleState): ModulePowerAction[] {
  switch (state) {
    case "NOT_INSTALLED":
    case "UNLINKED":
      return ["pair"];
    case "LINKED_OFF":
      return ["start", "disable", "revoke"];
    case "STARTING":
    case "AUTHENTICATING":
      return ["cancel"];
    case "READY":
    case "BUSY":
      return ["open", "stop", "restart"];
    case "STOPPING":
      return [];
    case "ERROR":
      return ["start", "disable", "revoke"];
    case "DISABLED":
      return ["enable", "revoke"];
    case "INCOMPATIBLE":
    case "QUARANTINED":
      return ["revoke"];
    case "PAIRING":
    case "REVOKED":
      return ["pair"];
  }
}
