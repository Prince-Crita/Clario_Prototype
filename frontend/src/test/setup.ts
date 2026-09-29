import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// jsdom gaps that Radix primitives rely on.
class NoopResizeObserver {
  observe(): void {
    // no-op: jsdom has no layout
  }
  unobserve(): void {
    // no-op: jsdom has no layout
  }
  disconnect(): void {
    // no-op: jsdom has no layout
  }
}
globalThis.ResizeObserver ??= NoopResizeObserver as unknown as typeof ResizeObserver;
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.releasePointerCapture ??= () => undefined;
Element.prototype.scrollIntoView ??= () => undefined;
