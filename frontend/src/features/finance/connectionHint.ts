/**
 * Which connection this browser last opened for a workspace's integration, remembered so the
 * dashboard can ask for its data at once instead of waiting to be told. It is only a hint: the
 * server still decides what the person may see, and a hint that has gone stale just makes a
 * speculative request fail quietly, after which the normal path runs. Not a secret (an id).
 */
const key = (workspaceId: string, integration: string) =>
  `clario:connection:${workspaceId}:${integration}`;

export function readConnectionHint(workspaceId: string, integration: string): string | null {
  try {
    return window.localStorage.getItem(key(workspaceId, integration));
  } catch {
    return null; // storage can be blocked or unavailable; the hint is optional
  }
}

export function rememberConnection(
  workspaceId: string,
  integration: string,
  connectionId: string,
): void {
  try {
    window.localStorage.setItem(key(workspaceId, integration), connectionId);
  } catch {
    // ignore: nothing depends on it
  }
}
