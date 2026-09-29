/**
 * How connection states and connect failures are worded — one place, used by the tile and pages.
 * Failure codes are the closed set the OAuth callback sends back as `?error=` (backend
 * `ConnectFailure`); anything else gets the generic message.
 */
import type { ConnectionState, IntegrationTile } from "../../lib/api/types";

type Tone = "neutral" | "positive" | "warning" | "negative" | "info";

export const STATE_STATUS: Record<ConnectionState, { label: string; tone: Tone }> = {
  not_connected: { label: "Not connected", tone: "neutral" },
  pending: { label: "Setup not finished", tone: "info" },
  connected: { label: "Connected", tone: "positive" },
  needs_reauth: { label: "Needs reconnecting", tone: "warning" },
  error: { label: "Connection problem", tone: "negative" },
  coming_soon: { label: "Coming soon", tone: "neutral" },
};

export function connectFailureMessage(code: string, tile: IntegrationTile): string {
  const { name, vendor, account_noun: noun } = tile;
  switch (code) {
    case "access_denied":
      return `Access wasn't approved in ${vendor}, so nothing was connected.`;
    case "state_invalid":
      return "That sign-in expired or was already used. Start again.";
    case "forbidden":
      return `Only workspace owners and admins can connect ${name}.`;
    case "missing_scopes":
      return `Some permissions weren't granted. Approve everything ${vendor} asks for — Clario's access is read-only.`;
    case "account_mismatch":
      return `The ${vendor} login you used can't see ${tile.connection?.account?.name ?? `this ${noun}`}. Reconnect with a login that has access to it.`;
    case "server_rejected":
      return `${vendor} sent Clario to an unexpected server, so the connection was stopped for safety. Try again, and contact Crita support if it happens again.`;
    case "exchange_failed":
      return `${vendor} didn't confirm the sign-in. Try again.`;
    default:
      return `${vendor} didn't respond as expected. Try again in a few minutes.`;
  }
}
