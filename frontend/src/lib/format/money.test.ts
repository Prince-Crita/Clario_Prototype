import { describe, expect, it } from "vitest";

import vectors from "../../../../contracts/money-format-vectors.json";
import { formatInr, formatInrCompact, formatPercent } from "./money";

describe("money formatting matches the shared contract (contracts/money-format-vectors.json)", () => {
  it.each(vectors.money)("formats $value ($decimals dp)", ({ value, decimals, full, compact }) => {
    expect(formatInr(value, decimals)).toBe(full);
    expect(formatInrCompact(value)).toBe(compact);
  });

  it.each(vectors.percent)("formats percent $value", ({ value, decimals, text }) => {
    expect(formatPercent(value, decimals)).toBe(text);
  });

  it("rejects non-decimal input rather than guessing", () => {
    expect(() => formatInr("12abc")).toThrow("Not a decimal string");
  });
});
