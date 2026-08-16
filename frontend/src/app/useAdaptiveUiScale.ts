import { useEffect } from "react";

const REFERENCE_WIDTH = 1440;
const REFERENCE_HEIGHT = 900;

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

export function calculateUiScale(width: number, height: number, preference = 1): number {
  const viewportScale = clamp(
    Math.min(width / REFERENCE_WIDTH, height / REFERENCE_HEIGHT),
    0.78,
    1.1,
  );
  return clamp(viewportScale * clamp(preference, 0.85, 1.3), 0.68, 1.32);
}

export function useAdaptiveUiScale(preference: number): void {
  useEffect(() => {
    const root = document.documentElement;
    let animationFrame = 0;

    const updateScale = () => {
      animationFrame = 0;
      const width = window.innerWidth;
      const height = window.innerHeight;
      const scale = calculateUiScale(width, height, preference);

      root.style.setProperty("--ui-scale", scale.toFixed(4));
      root.style.setProperty("--ui-layout-width", `${width / scale}px`);
      root.style.setProperty("--ui-layout-height", `${height / scale}px`);
      root.dataset.uiScale = `${Math.round(scale * 100)}`;
    };

    const scheduleUpdate = () => {
      if (animationFrame) window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(updateScale);
    };

    updateScale();
    window.addEventListener("resize", scheduleUpdate);
    window.visualViewport?.addEventListener("resize", scheduleUpdate);

    return () => {
      if (animationFrame) window.cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", scheduleUpdate);
      window.visualViewport?.removeEventListener("resize", scheduleUpdate);
    };
  }, [preference]);
}
