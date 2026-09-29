import { describe, expect, it } from "vitest";

import { niceScale } from "./components/scale";
import { dayLabel, isNegative, isZero, monthLabel } from "./format";

describe("finance display helpers", () => {
  it("formats labels and signs without arithmetic on figures", () => {
    expect(monthLabel("2026-03-01")).toMatch(/^Mar '26$/);
    expect(dayLabel("2026-09-25")).toMatch(/^25 Sept?$/);
    expect(isNegative("-648028.0000")).toBe(true);
    expect(isNegative("-0.0000")).toBe(false);
    expect(isZero("0.0000")).toBe(true);
  });

  it("chooses round axis steps that cover the data", () => {
    expect(niceScale([258_715, 36_000]).ticks).toEqual([
      0, 50_000, 100_000, 150_000, 200_000, 250_000, 300_000,
    ]);
    expect(niceScale([-91_549, 21_375]).ticks).toEqual([
      -100_000, -80_000, -60_000, -40_000, -20_000, 0, 20_000, 40_000,
    ]);
    expect(niceScale([]).ticks).toEqual([0]);
  });
});
