import { describe, expect, it } from "vitest";
import { calculateUiScale } from "./useAdaptiveUiScale";

describe("calculateUiScale", () => {
  it("uses the reference viewport at the neutral preference", () => {
    expect(calculateUiScale(1440, 900, 1)).toBe(1);
  });

  it("shrinks the whole interface for a smaller window", () => {
    expect(calculateUiScale(1280, 720, 1)).toBeCloseTo(0.8);
  });

  it("combines the automatic window scale with the saved preference", () => {
    expect(calculateUiScale(1440, 900, 1.2)).toBeCloseTo(1.2);
  });

  it("keeps extreme window sizes inside safe bounds", () => {
    expect(calculateUiScale(320, 240, 0.85)).toBe(0.68);
    expect(calculateUiScale(3840, 2160, 1.3)).toBe(1.32);
  });
});
