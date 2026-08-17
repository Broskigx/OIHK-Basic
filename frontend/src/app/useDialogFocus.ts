import { useEffect, type RefObject } from "react";

/**
 * Keyboard behaviour a dialog has to provide once it claims `aria-modal`.
 *
 * The attribute tells assistive technology that the rest of the page is inert.
 * Nothing enforces that: without a trap, Tab walks straight out of the dialog
 * and into content a screen reader has already been told is unreachable, which
 * is a worse state than never having claimed modality. This supplies the three
 * behaviours that make the claim true — focus moves in on open, Tab cycles
 * inside, and focus returns to whatever opened the dialog on close.
 *
 * `onDismiss` is optional because not every dialog may be dismissed: the
 * first-run flow has no cancel, so it gets the trap without the Escape key
 * rather than a key that appears to do nothing.
 */

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export function useDialogFocus(
  dialogRef: RefObject<HTMLElement | null>,
  { onDismiss }: { onDismiss?: () => void } = {},
): void {
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    // Deliberately not filtered by visibility. The obvious check —
    // `offsetParent !== null` — reports every element as hidden under jsdom,
    // which would make this untestable in exchange for a case these dialogs do
    // not have: they render their controls rather than hiding them in place.
    const focusableElements = (): HTMLElement[] =>
      Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));

    (focusableElements()[0] ?? dialog).focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && onDismiss) {
        event.preventDefault();
        onDismiss();
        return;
      }
      if (event.key !== "Tab") return;

      const elements = focusableElements();
      if (elements.length === 0) {
        // Nothing to cycle through, but focus must still not leave.
        event.preventDefault();
        dialog.focus();
        return;
      }

      const first = elements[0];
      const last = elements[elements.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || !dialog.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    // Capture phase: a field inside the dialog that handles Escape for its own
    // reasons should not be able to swallow the dismissal on the way up.
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      previouslyFocused?.focus?.();
    };
  }, [dialogRef, onDismiss]);
}
