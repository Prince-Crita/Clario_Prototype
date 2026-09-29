/** Human wording for enum values from the API — one place, so screens stay consistent. */
import type { Role } from "./api/types";

export const ROLE_LABEL: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  viewer: "Viewer",
};

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** 4 → "April–March" (fiscal year start month is 1-based). */
export function fiscalYearLabel(startMonth: number): string {
  const start = MONTHS[(startMonth - 1 + 12) % 12];
  const end = MONTHS[(startMonth - 2 + 12) % 12];
  return `${start}–${end}`;
}

/** Only allow in-app relative redirects (prevents open redirects via ?next=). */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/w";
}

/** "Asia/Kolkata" → "India Standard Time" (falls back to the id if the runtime lacks the zone). */
export function timeZoneLabel(timeZone: string): string {
  try {
    const parts = new Intl.DateTimeFormat("en-IN", {
      timeZone,
      timeZoneName: "long",
    }).formatToParts(new Date());
    return parts.find((part) => part.type === "timeZoneName")?.value ?? timeZone;
  } catch {
    return timeZone;
  }
}
