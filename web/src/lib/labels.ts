import type { Role } from "./api/types";

/** Human wording for enum values from the API — one place, so screens stay consistent. */
export const ROLE_LABEL: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  viewer: "Viewer",
};

/** Only allow in-app relative redirects (prevents open redirects via ?next=). */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\")
    ? next
    : "/w";
}
