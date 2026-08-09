export type SystemLinkModuleState =
  | "NOT_INSTALLED"
  | "UNLINKED"
  | "PAIRING"
  | "LINKED_OFF"
  | "STARTING"
  | "AUTHENTICATING"
  | "READY"
  | "BUSY"
  | "STOPPING"
  | "ERROR"
  | "INCOMPATIBLE"
  | "REVOKED"
  | "DISABLED"
  | "QUARANTINED";

export type SystemLinkCategory = {
  id: string;
  route_id: string;
  label: string;
  icon: string;
  case_scoped: boolean;
  order: number;
  enabled: boolean;
};

export type LinkedSystemModule = {
  module_id: string;
  product_name: string;
  module_version: string;
  protocol_version: string;
  state: SystemLinkModuleState;
  installed: boolean;
  linked: boolean;
  enabled: boolean;
  module_fingerprint: string;
  package_sha256: string;
  granted_capabilities: string[];
  requested_capabilities: string[];
  categories: SystemLinkCategory[];
  startup_policy: "manual" | "start-with-basic" | "restore-last-state";
  last_handshake_at: string | null;
  last_health_at: string | null;
  last_error_code: string;
  last_error_detail: string;
};

export type SystemLinkStatus = {
  protocol_version: string;
  installation_public_key: string;
  installation_fingerprint: string;
  key_storage: string;
  modules: LinkedSystemModule[];
};

export type PairingStart = {
  pairing_id: string;
  link_key: string;
  expires_at: string;
  challenge: string;
  protocol_version: string;
  installation_public_key: string;
  installation_fingerprint: string;
  basic_signature: string;
};

export type PendingPairing = {
  pairing_id: string;
  module_id: string;
  product_name: string;
  module_version: string;
  module_fingerprint: string;
  requested_capabilities: string[];
  categories: Array<Record<string, unknown>>;
  expires_at: string;
};

export type LifecycleResult = {
  module_id: string;
  state: SystemLinkModuleState;
  action: string;
  detail: string;
};

export type ModuleLifecycleAction = "start" | "stop" | "restart" | "cancel" | "disable" | "enable" | "revoke";
