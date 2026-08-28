import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CustodyReport, EvidenceItem } from "../../types";
import { CustodyRegisterView } from "./CustodyRegisterView";

const apiMocks = vi.hoisted(() => ({
  list: vi.fn(),
  verify: vi.fn(),
  remove: vi.fn(),
  manifest: vi.fn(),
}));

vi.mock("../../api", () => ({
  listEvidence: apiMocks.list,
  verifyEvidence: apiMocks.verify,
  deleteEvidence: apiMocks.remove,
  downloadEvidenceManifest: apiMocks.manifest,
}));

function exhibit(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: "evidence-1",
    case_id: "case-1",
    source_id: "source-1",
    original_name: "exhibit.bin",
    mime_type: "application/octet-stream",
    size_bytes: 2048,
    sha256: "a".repeat(64),
    notes: "",
    tags: [],
    entity_ids: [],
    ingested_by: "module:oihk.evidence-lab",
    original_reference: "",
    held_by_basic: true,
    export_count: 0,
    created_at: "2026-08-27T00:00:00Z",
    updated_at: "2026-08-27T00:00:00Z",
    verified_at: null,
    last_verification_intact: null,
    ...overrides,
  };
}

const intactChain: CustodyReport = {
  case_id: "case-1",
  intact: true,
  sealed_count: 2,
  first_broken_sequence: null,
  entries: [],
};

async function render(node: React.ReactElement): Promise<HTMLElement> {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(node);
  });
  return host;
}

function buttonLabelled(host: HTMLElement, text: string): HTMLButtonElement | undefined {
  return [...host.querySelectorAll("button")].find((button) => button.textContent?.includes(text)) as
    | HTMLButtonElement
    | undefined;
}

afterEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = "";
});

describe("custody register", () => {
  it("sends an operator with an empty register to System Link, not to a dead end", async () => {
    // Basic cannot acquire evidence on its own any more, so "nothing here yet"
    // has to say what would put something here.
    apiMocks.list.mockResolvedValue([]);
    const host = await render(
      <CustodyRegisterView
        caseId="case-1"
        custody={intactChain}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(host.textContent).toContain("Nothing in custody yet");
    expect(host.textContent).toContain("Evidence Lab");
    expect(buttonLabelled(host, "Linked modules")).toBeDefined();
  });

  it("lists what the case holds with its digest and attribution", async () => {
    apiMocks.list.mockResolvedValue([exhibit()]);
    const host = await render(
      <CustodyRegisterView
        caseId="case-1"
        custody={intactChain}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(host.textContent).toContain("exhibit.bin");
    expect(host.textContent).toContain("2 KB");
    expect(host.textContent).toContain("oihk.evidence-lab");
    expect(host.textContent).toContain("Chain intact");
  });

  it("does not offer verification for an exhibit Basic does not hold", async () => {
    // The route answers 409 for these. A button that cannot succeed is worse
    // than no button: it invites the operator to read absence as tampering.
    apiMocks.list.mockResolvedValue([
      exhibit({ held_by_basic: false, original_reference: "evidence-lab://vault/disk.dd" }),
    ]);
    const host = await render(
      <CustodyRegisterView
        caseId="case-1"
        custody={intactChain}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(buttonLabelled(host, "Verify")?.disabled).toBe(true);
    expect(host.textContent).toContain("Linked module");
  });

  it("reports a failed verification as a mismatch against the seal", async () => {
    // The row re-reads from the backend after verifying, so what it shows is
    // what a reload would show -- not a verdict living only in this tab.
    apiMocks.list
      .mockResolvedValueOnce([exhibit()])
      .mockResolvedValue([
        exhibit({ verified_at: "2026-08-27T01:00:00Z", last_verification_intact: false }),
      ]);
    apiMocks.verify.mockResolvedValue({
      id: "evidence-1",
      expected_sha256: "a".repeat(64),
      actual_sha256: "b".repeat(64),
      intact: false,
      verified_at: "2026-08-27T01:00:00Z",
    });
    const host = await render(
      <CustodyRegisterView
        caseId="case-1"
        custody={intactChain}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    await act(async () => {
      buttonLabelled(host, "Verify")?.click();
    });
    expect(apiMocks.verify).toHaveBeenCalledWith("evidence-1");
    expect(host.textContent).toContain("Does not match its seal");
  });

  it("asks before removing an exhibit and does nothing if refused", async () => {
    apiMocks.list.mockResolvedValue([exhibit()]);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const host = await render(
      <CustodyRegisterView
        caseId="case-1"
        custody={intactChain}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    await act(async () => {
      buttonLabelled(host, "Remove")?.click();
    });
    expect(confirm).toHaveBeenCalled();
    expect(apiMocks.remove).not.toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("surfaces a broken chain rather than burying it in the table", async () => {
    apiMocks.list.mockResolvedValue([exhibit()]);
    const host = await render(
      <CustodyRegisterView
        caseId="case-1"
        custody={{ ...intactChain, intact: false, first_broken_sequence: 4 }}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(host.textContent).toContain("Chain broken");
    expect(host.textContent).toContain("4");
  });

  it("does not call the API without an investigation", async () => {
    const host = await render(
      <CustodyRegisterView
        caseId=""
        custody={null}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(apiMocks.list).not.toHaveBeenCalled();
    expect(host.textContent).toContain("No active investigation");
  });

  it("shows a remembered mismatch without anyone pressing Verify", async () => {
    // The state a custody register can least afford to lose: a failed check
    // recorded yesterday has to be the first thing visible today.
    apiMocks.list.mockResolvedValue([
      exhibit({ verified_at: "2026-08-27T01:00:00Z", last_verification_intact: false }),
    ]);
    const host = await render(
      <CustodyRegisterView
        caseId="case-1"
        custody={intactChain}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(apiMocks.verify).not.toHaveBeenCalled();
    expect(host.textContent).toContain("Does not match its seal");
    expect(host.textContent).toContain("1 exhibit no longer matches its seal.");
  });

  it("agrees with itself about how many exhibits failed", async () => {
    // Singular and plural take different sentences: "1 exhibit no longer match
    // their seal" is the kind of wrong that makes a report look unreviewed.
    apiMocks.list.mockResolvedValue([
      exhibit({ id: "a", verified_at: "2026-08-27T01:00:00Z", last_verification_intact: false }),
      exhibit({ id: "b", verified_at: "2026-08-27T01:00:00Z", last_verification_intact: false }),
    ]);
    const host = await render(
      <CustodyRegisterView
        caseId="case-1"
        custody={intactChain}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(host.textContent).toContain("2 exhibits no longer match their seals.");
  });

  it("does not claim a pass for a row checked before verdicts were recorded", async () => {
    apiMocks.list.mockResolvedValue([
      exhibit({ verified_at: "2026-08-27T01:00:00Z", last_verification_intact: null }),
    ]);
    const host = await render(
      <CustodyRegisterView
        caseId="case-1"
        custody={intactChain}
        onOpenSystemLink={vi.fn()}
        onOpenInvestigations={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(host.textContent).toContain("Checked before verdicts were recorded");
    expect(host.textContent).not.toContain("Matches its seal");
  });
});
