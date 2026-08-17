import { act, useRef } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useDialogFocus } from "./useDialogFocus";

function Dialog({ onDismiss }: { onDismiss?: () => void }) {
  const dialogRef = useRef<HTMLElement>(null);
  useDialogFocus(dialogRef, { onDismiss });
  return (
    <section ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Test dialog">
      <button type="button" id="first">First</button>
      <input id="middle" />
      <button type="button" id="last">Last</button>
    </section>
  );
}

let unmountCurrent: (() => void) | null = null;

async function open(onDismiss?: () => void): Promise<void> {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<Dialog onDismiss={onDismiss} />);
  });
  unmountCurrent = () => act(() => root.unmount());
}

function press(key: string, options: { shiftKey?: boolean } = {}): void {
  act(() => {
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...options }),
    );
  });
}

afterEach(() => {
  unmountCurrent?.();
  unmountCurrent = null;
  document.body.innerHTML = "";
});

describe("useDialogFocus", () => {
  it("moves focus into the dialog when it opens", async () => {
    await open();

    expect(document.activeElement?.id).toBe("first");
  });

  it("wraps forward from the last control back to the first", async () => {
    await open();
    document.querySelector<HTMLElement>("#last")!.focus();

    press("Tab");

    expect(document.activeElement?.id).toBe("first");
  });

  it("wraps backward from the first control to the last", async () => {
    await open();

    press("Tab", { shiftKey: true });

    expect(document.activeElement?.id).toBe("last");
  });

  it("pulls focus back in when it has escaped the dialog", async () => {
    await open();
    const outside = document.createElement("button");
    document.body.appendChild(outside);
    outside.focus();

    press("Tab", { shiftKey: true });

    expect(document.activeElement?.id).toBe("last");
  });

  it("dismisses on Escape when the dialog can be closed", async () => {
    const onDismiss = vi.fn();
    await open(onDismiss);

    press("Escape");

    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("ignores Escape when the dialog has no way to be closed", async () => {
    await open();

    // The assertion that matters is that nothing throws and focus stays put:
    // first run has no cancel, so the key must be inert rather than bound to
    // something that commits.
    press("Escape");

    expect(document.activeElement?.id).toBe("first");
  });

  it("returns focus to whatever opened the dialog", async () => {
    const opener = document.createElement("button");
    document.body.appendChild(opener);
    opener.focus();

    await open();
    expect(document.activeElement?.id).not.toBe(undefined);

    unmountCurrent?.();
    unmountCurrent = null;

    expect(document.activeElement).toBe(opener);
  });
});
