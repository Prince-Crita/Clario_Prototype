import { ApiError, apiFetch, setCsrfToken } from "../../lib/api/client";
import type { Session } from "../../lib/api/types";

/** Current session, or null when signed out. Keeps the CSRF token in sync. */
export async function fetchSession(): Promise<Session | null> {
  try {
    const session = await apiFetch<Session>("/auth/session");
    setCsrfToken(session.csrf_token);
    return session;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      setCsrfToken(null);
      return null;
    }
    throw error;
  }
}

export async function signIn(email: string, password: string): Promise<Session> {
  const session = await apiFetch<Session>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
  setCsrfToken(session.csrf_token);
  return session;
}

export async function signOut(): Promise<void> {
  try {
    await apiFetch<undefined>("/auth/logout", { method: "POST" });
  } finally {
    setCsrfToken(null);
  }
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiFetch<undefined>("/auth/password", {
    method: "POST",
    body: { current_password: currentPassword, new_password: newPassword },
  });
}
