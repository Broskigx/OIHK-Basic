import { act, useRef } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useInterfaceMotion } from "./useInterfaceMotion";

const animeMocks = vi.hoisted(() => ({
  animate: vi.fn((targets: unknown, options: unknown) => ({ cancel: vi.fn(), targets, options })),
  stagger: vi.fn((step: number) => step),
}));

vi.mock("animejs", () => ({
  animate: animeMocks.animate,
  stagger: animeMocks.stagger,
}));

/**
 * Anime.js accepts an empty target list: it warns on the console and hands back
 * an animation that drives nothing. That makes an unguarded call silent in the
 * type checker and silent in the tests, which is why the guard is asserted here
 * rather than left to review.
 */
function receivedAnEmptyTargetList(): boolean {
  return animeMocks.animate.mock.calls.some(([target]) => {
    if (typeof target !== "object" || target === null) return false;
    return "length" in target && (target as ArrayLike<unknown>).length === 0;
  });
}

function Harness({ withChrome }: { withChrome: boolean }) {
  const shellRef = useRef<HTMLElement>(null);
  useInterfaceMotion("dashboard", shellRef);
  return (
    <main ref={shellRef}>
      {withChrome ? <button className="platform-nav-item active">Dashboard</button> : null}
    </main>
  );
}

async function render(withChrome: boolean): Promise<() => void> {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<Harness withChrome={withChrome} />);
  });
  return () => act(() => root.unmount());
}

beforeEach(() => {
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    callback(0);
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {});
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    media: "",
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  document.documentElement.classList.remove("reduce-motion");
  document.body.innerHTML = "";
});

describe("useInterfaceMotion", () => {
  it("animates nothing when the shell has no animatable surfaces yet", async () => {
    const unmount = await render(false);

    expect(receivedAnEmptyTargetList()).toBe(false);
    expect(animeMocks.animate).not.toHaveBeenCalled();

    unmount();
  });

  it("animates the surfaces that are present", async () => {
    const unmount = await render(true);

    expect(animeMocks.animate).toHaveBeenCalled();
    expect(receivedAnEmptyTargetList()).toBe(false);

    unmount();
  });

  it("stands down entirely when the interface asks for reduced motion", async () => {
    document.documentElement.classList.add("reduce-motion");

    const unmount = await render(true);

    expect(animeMocks.animate).not.toHaveBeenCalled();

    unmount();
  });

  it("respects the operating system reduced-motion preference", async () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: true,
      media: "(prefers-reduced-motion: reduce)",
      addEventListener: () => {},
      removeEventListener: () => {},
    }));

    const unmount = await render(true);

    expect(animeMocks.animate).not.toHaveBeenCalled();

    unmount();
  });
});
