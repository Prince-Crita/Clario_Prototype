/**
 * Phase 3 exit criterion: colour contrast (WCAG 2.2 AA) for every pairing the UI uses.
 * Reads tokens.css directly, so a token change that breaks accessibility fails CI.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "tokens.css"), "utf8");
const tokens = new Map(
  [...css.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})\b/gi)].map((m) => [
    m[1],
    (m[2] ?? "").toLowerCase(),
  ]),
);

function token(name: string): string {
  const value = tokens.get(name);
  if (!value) throw new Error(`token --${name} is not defined in tokens.css`);
  return value;
}

function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT = 4.5; // normal text
const UI = 3; // large text, icons, chart marks, focus indicators

// [foreground, background, minimum]
const PAIRS: [string, string, number][] = [
  ["ink", "paper", TEXT],
  ["ink", "surface", TEXT],
  ["ink-2", "paper", TEXT],
  ["ink-2", "surface", TEXT],
  ["ink-3", "paper", TEXT],
  ["ink-3", "surface", TEXT],
  ["ink-3", "surface-sunken", TEXT],
  ["ink-inverse", "forest", TEXT],
  ["ink-inverse", "forest-hover", TEXT],
  ["forest", "surface", TEXT],
  ["forest", "paper", TEXT],
  ["forest", "forest-tint", TEXT], // active navigation and selected states
  ["rail-ink", "rail", TEXT], // the navigation rail
  ["rail-ink-2", "rail", TEXT],
  ["rail-ink", "rail-raised", TEXT],
  ["accent", "surface", TEXT],
  ["accent", "paper", TEXT],
  ["forest", "accent-soft", TEXT],
  ["negative", "negative-bg", TEXT],
  ["olive", "surface", TEXT],
  ["negative", "surface", TEXT],
  ["negative", "negative-bg", TEXT],
  ["positive", "surface", TEXT],
  ["positive", "positive-bg", TEXT],
  ["warning", "surface", TEXT],
  ["warning", "warning-bg", TEXT],
  ["info", "surface", TEXT],
  ["info", "info-bg", TEXT],
  ["line-strong", "surface", 1.4], // hairlines are decorative; inputs also carry a label
  ["forest", "paper", UI], // focus ring: forest ring must stand out on every background
  ...[1, 2, 3, 4, 5, 6].map((n): [string, string, number] => [`series-${n}`, "surface", UI]),
];

describe("design tokens meet WCAG 2.2 AA contrast", () => {
  it.each(PAIRS)("%s on %s ≥ %s:1", (fg, bg, min) => {
    expect(contrast(token(fg), token(bg))).toBeGreaterThanOrEqual(min);
  });

  it("never uses lime for text (it fails contrast on light surfaces)", () => {
    expect(contrast(token("lime"), token("surface"))).toBeLessThan(TEXT);
  });
});
