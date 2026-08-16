/** Node type definitions, colors, shapes, and category groupings for the intelligence graph */

export type NodeCategory =
  | "person"      // names, handles, friends, family
  | "contact"     // email, phone
  | "infra"       // IP, domain, host, ASN
  | "web"         // URL, website
  | "org"         // organization
  | "evidence"    // source, photo, file
  | "crypto"      // cryptocurrency
  | "other";      // notes, misc

export interface NodeTypeConfig {
  type: string;
  label: string;
  category: NodeCategory;
  color: string;
  borderColor: string;
  shape: "circle" | "square" | "diamond" | "hexagon" | "triangle";
  icon?: string;
}

const NODE_TYPE_CONFIGS: Record<string, NodeTypeConfig> = {
  name:         { type: "name",         label: "Persona",         category: "person",   color: "#4ade80", borderColor: "#166534", shape: "circle" },
  handle:       { type: "handle",       label: "Handle/Alias",    category: "person",   color: "#c084fc", borderColor: "#7c3aed", shape: "circle" },
  friend:       { type: "friend",       label: "Amigo/Familiar",  category: "person",   color: "#f472b6", borderColor: "#be185d", shape: "circle" },
  family:       { type: "family",       label: "Familiar",        category: "person",   color: "#fb7185", borderColor: "#be123c", shape: "circle" },
  email:        { type: "email",        label: "Email",           category: "contact",  color: "#2dd4bf", borderColor: "#0d9488", shape: "square" },
  phone:        { type: "phone",        label: "Teléfono",        category: "contact",  color: "#fbbf24", borderColor: "#b45309", shape: "square" },
  ip:           { type: "ip",           label: "Dirección IP",    category: "infra",    color: "#fb923c", borderColor: "#c2410c", shape: "diamond" },
  domain:       { type: "domain",       label: "Dominio",         category: "infra",    color: "#38bdf8", borderColor: "#0369a1", shape: "diamond" },
  host:         { type: "host",         label: "Host",            category: "infra",    color: "#7dd3fc", borderColor: "#0ea5e9", shape: "diamond" },
  asn:          { type: "asn",          label: "ASN",             category: "infra",    color: "#a78bfa", borderColor: "#6d28d9", shape: "diamond" },
  url:          { type: "url",          label: "URL/Sitio web",   category: "web",      color: "#a78bfa", borderColor: "#6d28d9", shape: "hexagon" },
  website:      { type: "website",      label: "Sitio web",       category: "web",      color: "#818cf8", borderColor: "#4338ca", shape: "hexagon" },
  subdomain:    { type: "subdomain",    label: "Subdominio",      category: "web",      color: "#93c5fd", borderColor: "#2563eb", shape: "hexagon" },
  organization: { type: "organization", label: "Organización",    category: "org",      color: "#f87171", borderColor: "#b91c1c", shape: "square" },
  org:          { type: "org",          label: "Organización",    category: "org",      color: "#f87171", borderColor: "#b91c1c", shape: "square" },
  source:       { type: "source",       label: "Fuente",          category: "evidence", color: "#94a3b8", borderColor: "#475569", shape: "triangle" },
  photo:        { type: "photo",        label: "Foto",            category: "evidence", color: "#fbbf24", borderColor: "#b45309", shape: "triangle" },
  evidence:     { type: "evidence",     label: "Evidencia",       category: "evidence", color: "#a3e635", borderColor: "#4d7c0f", shape: "triangle" },
  crypto:       { type: "crypto",       label: "Criptomoneda",    category: "crypto",   color: "#facc15", borderColor: "#a16207", shape: "hexagon" },
  file:         { type: "file",         label: "Archivo",         category: "evidence", color: "#fda4af", borderColor: "#9f1239", shape: "square" },
  hash:         { type: "hash",         label: "Hash",            category: "evidence", color: "#c4b5fd", borderColor: "#6d28d9", shape: "square" },
  location:     { type: "location",     label: "Ubicación",       category: "other",    color: "#6ee7b7", borderColor: "#047857", shape: "circle" },
  username:     { type: "username",     label: "Usuario",         category: "person",   color: "#f9a8d4", borderColor: "#be185d", shape: "circle" },
  custom:       { type: "custom",       label: "Entidad personalizada", category: "other", color: "#e2e8f0", borderColor: "#64748b", shape: "hexagon" },
  cve:          { type: "cve",          label: "CVE",             category: "other",    color: "#fda4af", borderColor: "#9f1239", shape: "diamond" },
  btc:          { type: "btc",          label: "Bitcoin",         category: "crypto",   color: "#facc15", borderColor: "#a16207", shape: "hexagon" },
  eth:          { type: "eth",          label: "Ethereum",        category: "crypto",   color: "#94a3b8", borderColor: "#475569", shape: "hexagon" },
  note:         { type: "note",         label: "Nota",            category: "other",    color: "#e2e8f0", borderColor: "#64748b", shape: "square" },
};

// Aliases — extra producer types (IOC extractor, forensics, upstream tools) that
// render with the visual identity of their canonical counterpart. These are
// intentional shared references: never mutate a returned NodeTypeConfig.
NODE_TYPE_CONFIGS.user = NODE_TYPE_CONFIGS.username;
NODE_TYPE_CONFIGS.ipv4 = NODE_TYPE_CONFIGS.ip;
NODE_TYPE_CONFIGS.md5 = NODE_TYPE_CONFIGS.hash;
NODE_TYPE_CONFIGS.sha1 = NODE_TYPE_CONFIGS.hash;
NODE_TYPE_CONFIGS.sha256 = NODE_TYPE_CONFIGS.hash;

export const CATEGORY_LABELS: Record<NodeCategory, string> = {
  person:   "Personas & Contactos",
  contact:  "Medios de contacto",
  infra:    "Infraestructura",
  web:      "Web & Subdominios",
  org:      "Organizaciones",
  evidence: "Evidencia & Fuentes",
  crypto:   "Criptoactivos",
  other:    "Otros",
};

export const CATEGORY_ORDER: NodeCategory[] = [
  "person", "contact", "infra", "web", "org", "evidence", "crypto", "other",
];

export const CATEGORY_COLORS: Record<NodeCategory, string> = {
  person:   "#4ade80",
  contact:  "#2dd4bf",
  infra:    "#fb923c",
  web:      "#a78bfa",
  org:      "#f87171",
  evidence: "#94a3b8",
  crypto:   "#facc15",
  other:    "#e2e8f0",
};

export function getNodeConfig(type: string): NodeTypeConfig {
  return NODE_TYPE_CONFIGS[type] ?? {
    type,
    label: type,
    category: "other",
    color: "#94a3b8",
    borderColor: "#475569",
    shape: "circle",
  };
}

export function getCategory(type: string): NodeCategory {
  return getNodeConfig(type).category;
}
