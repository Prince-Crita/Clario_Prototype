/** Series colours from tokens, in legend order (billed, collected, expenses, …). */
export const SERIES_COUNT = 6;

export function seriesColour(index: number): string {
  return `var(--series-${(index % SERIES_COUNT) + 1})`;
}
