/**
 * The AI usage-limit countdown. The server sends how many seconds remain (the latest reset among
 * the provider's exhausted limits); counting from when that reply arrived keeps the countdown
 * independent of the browser's clock. When it reaches zero the panel asks the server again, and
 * the server says "unconfirmed" (not "available") until a real answer gets through.
 */
import { useEffect, useState } from "react";

/** 31331 → "8h 42m" · 252 → "4m 12s" · 9 → "9s" */
export function formatWait(seconds: number): string {
  const total = Math.max(1, Math.ceil(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours) return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
  if (minutes) return rest ? `${minutes}m ${rest}s` : `${minutes}m`;
  return `${rest}s`;
}

const CLOCK = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" });

/** "12:47 am": a fixed time for screen readers, so a ticking countdown is never announced. */
export const clockTime = (reportedAt: number, seconds: number): string =>
  CLOCK.format(new Date(reportedAt + seconds * 1000));

/** Seconds left of a server-reported wait (null when none was reported); calls `onDone` at zero. */
export function useCountdown(
  seconds: number | null | undefined,
  reportedAt: number,
  onDone: () => void,
): number | null {
  const [now, setNow] = useState(() => Date.now());
  const left =
    seconds === null || seconds === undefined
      ? null
      : Math.max(0, seconds - Math.max(0, now - reportedAt) / 1000);

  useEffect(() => {
    if (left === null) return;
    if (left <= 0) {
      onDone();
      return;
    }
    const timer = window.setTimeout(() => setNow(Date.now()), Math.min(left * 1000, 1000));
    return () => window.clearTimeout(timer);
  }, [left, onDone]);

  return left;
}
