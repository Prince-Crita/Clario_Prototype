/** Join class names, skipping falsy values. Always returns a string (CSS-module lookups may be undefined). */
export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
