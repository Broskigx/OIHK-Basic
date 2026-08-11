export type GraphShortcut =
  | "focus-search"
  | "select-all"
  | "undo"
  | "redo"
  | "clear-selection"
  | "delete-selection"
  | "fit-view"
  | "dismiss-input";

export function resolveGraphShortcut(input: {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
  editable?: boolean;
}): GraphShortcut | null {
  if (input.editable) return input.key === "Escape" ? "dismiss-input" : null;

  const command = Boolean(input.ctrlKey || input.metaKey);
  const key = input.key.toLowerCase();
  if (command && key === "f") return "focus-search";
  if (command && key === "a") return "select-all";
  if (command && key === "z") return input.shiftKey ? "redo" : "undo";
  if (input.key === "Escape") return "clear-selection";
  if (input.key === "Delete") return "delete-selection";
  if (!command && !input.altKey && key === "f") return "fit-view";
  return null;
}
