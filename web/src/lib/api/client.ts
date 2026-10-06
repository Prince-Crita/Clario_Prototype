/**
 * The ONLY module that talks HTTP. Components and hooks never call `fetch` directly.
 *
 * Production authentication is a Bearer token (not cookies, not CSRF):
 *   Authorization: Bearer <access_token>      from localStorage "clario.token"
 *   X-Tenant-Id:   <workspace id>             from localStorage "clario.tenantId"
 * Errors from the backend look like { "detail": "message" } or, for validation (422),
 * { "detail": [{ "loc": ["body","email"], "msg": "..." }] }.
 */

// Development: Vite forwards /api to the backend. If the app is ever hosted under a prefix
// (e.g. /clario), set VITE_API_BASE to "/clario/api" at build time.
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "/api";

// ---------------------------------------------------------------------------------------------
// Auth storage. Same keys as the legacy app, so both apps can share a signed-in session.
// ---------------------------------------------------------------------------------------------
const TOKEN_KEY = "clario.token";
const TENANT_KEY = "clario.tenantId";
// The legacy app also keeps chat ids; clear them on sign-out so nothing stale is left behind.
const LEGACY_KEYS = ["clario.sessionId", "clario.conversationId"];

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // storage can be blocked (private mode); behave as signed out
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // ignore: nothing useful to do if storage is blocked
  }
}

export const getToken = (): string | null => read(TOKEN_KEY);
export const setToken = (token: string | null): void => write(TOKEN_KEY, token);
export const getTenantId = (): string | null => read(TENANT_KEY);
export const setTenantId = (id: string | null): void => write(TENANT_KEY, id);

/** Sign-out: forget the token, the selected workspace and any legacy chat ids. */
export function clearAuthStorage(): void {
  write(TOKEN_KEY, null);
  write(TENANT_KEY, null);
  for (const key of LEGACY_KEYS) write(key, null);
}

// ---------------------------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------------------------
export interface FieldError {
  /** The input name, e.g. "email". */
  field: string;
  message: string;
}

export class ApiError extends Error {
  /** HTTP status; 0 means the server could not be reached. */
  readonly status: number;
  /** One readable sentence, safe to show to the user. */
  readonly detail: string;
  /** Per-field problems from a 422 response; empty otherwise. */
  readonly fields: FieldError[];

  constructor(status: number, detail: string, fields: FieldError[] = []) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.fields = fields;
  }
}

const NETWORK_MESSAGE = "Clario can't be reached right now. Check your connection and try again.";
const GENERIC_MESSAGE = "Something went wrong. Try again.";

interface ValidationItem {
  loc?: unknown[];
  msg?: string;
}

/** Turns the backend's `detail` (string, or a list for 422) into a message and field errors. */
function parseDetail(detail: unknown): { message: string; fields: FieldError[] } {
  if (typeof detail === "string" && detail) return { message: detail, fields: [] };
  if (Array.isArray(detail)) {
    const fields: FieldError[] = (detail as ValidationItem[]).map((item) => ({
      field: String(item.loc?.[item.loc.length - 1] ?? ""),
      message: item.msg ?? "Invalid value.",
    }));
    return { message: "Some details are not valid. Check them and try again.", fields };
  }
  return { message: GENERIC_MESSAGE, fields: [] };
}

// ---------------------------------------------------------------------------------------------
// 401 handling
// ---------------------------------------------------------------------------------------------
let onUnauthorized: (() => void) | null = null;

/** The app registers one handler (clear cached data, go to /login). Pass null to remove it. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

// ---------------------------------------------------------------------------------------------
// The one request function
// ---------------------------------------------------------------------------------------------
interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** Sent as JSON. */
  body?: unknown;
  signal?: AbortSignal;
  /** Public endpoints (login): no token or tenant header, and a 401 is a normal answer. */
  skipAuth?: boolean;
}

export async function apiFetch<T>(
  path: string,
  { method = "GET", body, signal, skipAuth = false }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (!skipAuth) {
    const token = getToken();
    const tenantId = getTenantId();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (tenantId) headers["X-Tenant-Id"] = tenantId;
  }

  let response: Response;
  try {
    // The one sanctioned fetch call in the whole app.
    response = await fetch(`${API_BASE}${path.startsWith("/") ? path : `/${path}`}`, {
      method,
      headers,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      ...(signal ? { signal } : {}),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, NETWORK_MESSAGE);
  }

  if (response.status === 204) return undefined as T;
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const raw = (payload as { detail?: unknown } | null)?.detail;
    const { message, fields } = parseDetail(raw);
    // A 401 on a signed-in request means the session ended: forget it and tell the app.
    if (response.status === 401 && !skipAuth) {
      clearAuthStorage();
      onUnauthorized?.();
    }
    throw new ApiError(response.status, message, fields);
  }
  return payload as T;
}
