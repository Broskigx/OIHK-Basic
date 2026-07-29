import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { GraphWorkspaceView } from "./GraphWorkspaceView";

function renderGraphWorkspace(label = "") {
  return renderToString(
    createElement(GraphWorkspaceView, {
      graph: { nodes: [], edges: [] },
      analytics: null,
      selectedNode: null,
      openedNode: null,
      zoom: 1,
      layoutVersion: 0,
      showFilters: false,
      expanding: false,
      caseId: "case-1",
      manualEntity: { label, type: "name", confidence: 0.8, relation_label: "related_to" },
      onManualEntityChange: vi.fn(),
      onAddEntity: vi.fn(),
      onSelectNode: vi.fn(),
      onOpenNode: vi.fn(),
      onExpandNode: vi.fn(),
      onEnrichNode: vi.fn(),
      onRunTransform: vi.fn(),
      onRunAdhocMachine: vi.fn(),
      onRunSavedMachine: vi.fn(),
      onImportCsv: vi.fn(),
      onGraphChanged: vi.fn(async () => undefined),
      onToggleFilters: vi.fn(),
      onResetLayout: vi.fn(),
      onOpenEntityManager: vi.fn(),
      onError: vi.fn(),
    }),
  );
}

describe("GraphWorkspaceView", () => {
  it("exposes manual entity creation in the active graph workspace", () => {
    const emptyMarkup = renderGraphWorkspace();
    expect(emptyMarkup).toContain('aria-label="New entity label"');
    expect(emptyMarkup).toContain("Add to graph");
    expect(emptyMarkup).toContain('disabled=""');

    const populatedMarkup = renderGraphWorkspace("Example Entity");
    expect(populatedMarkup).toContain("Example Entity");
    expect(populatedMarkup).not.toContain('disabled=""');
  });
});
