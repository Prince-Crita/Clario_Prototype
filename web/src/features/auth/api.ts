import {
  ApiError,
  apiFetch,
  clearAuthStorage,
  getToken,
  setTenantId,
  setToken,
} from "../../lib/api/client";
import type { Role, Session, WorkspaceSummary } from "../../lib/api/types";

// ---- Response shapes of the two backend endpoints we call (see bruno-api-documentation) ----

/** POST /api/auth/login → 200 */
interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  /** The user's first workspace (by name), or null when they have none. */
  tenant_id: string | null;
}

/** GET /api/me → 200. Only the fields we read; the backend sends more. */
interface MeResponse {
  id: string;
  email: string;
  full_name: string;
  is_platform_admin: boolean;
  tenants: {
    id: string;
    slug: string;
    name: string;
    status: string;
    role: Role;
    zoho: {
      is_connected: boolean;
      organization_name: string;
      currency_code: string;
    };
  }[];
}

/** Backend response → our own model. Keeps only what the UI needs. */
function toSession(me: MeResponse): Session {
  const workspaces: WorkspaceSummary[] = me.tenants.map((t) => ({
    id: t.id,
    slug: t.slug,
    name: t.name,
    status: t.status,
    role: t.role,
    zoho: {
      is_connected: t.zoho.is_connected,
      organization_name: t.zoho.organization_name,
      currency_code: t.zoho.currency_code,
    },
  }));
  return {
    user: {
      id: me.id,
      email: me.email,
      full_name: me.full_name,
      is_platform_admin: me.is_platform_admin,
    },
    workspaces,
  };
}

/**
 * The current session, or null when signed out.
 * No token → null without calling the server. A 401 means the token expired or is invalid:
 * the client has already cleared the storage, so we simply report "signed out".
 */
export async function fetchSession(): Promise<Session | null> {
  if (!getToken()) return null;
  try {
    return toSession(await apiFetch<MeResponse>("/me"));
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

/**
 * Sign in: POST /api/auth/login, keep the token, then GET /api/me to build the session.
 * Wrong email or password rejects with an ApiError (401, "Invalid email or password.").
 */
export async function signIn(email: string, password: string): Promise<Session> {
  // `skipAuth`: login is public, and a 401 here is a normal "wrong password" answer.
  const login = await apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
    skipAuth: true,
  });

  setToken(login.access_token);
  // Replaces any older value (clears it when the user has no workspace yet).
  setTenantId(login.tenant_id);

  try {
    const session = await fetchSession();
    if (!session) throw new ApiError(401, "Your session could not be started. Try again.");
    return session;
  } catch (error) {
    // Do not stay half signed in (token stored but no session).
    clearAuthStorage();
    throw error;
  }
}

/**
 * Sign out. The backend has no logout endpoint (the token simply expires), so this only forgets
 * the token, the selected workspace and the legacy chat ids on this device.
 */
export function signOut(): void {
  clearAuthStorage();
}
