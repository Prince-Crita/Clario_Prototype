/**
 * The only module that talks HTTP (plan §9.2; `fetch` is banned elsewhere by ESLint).
 *
 * - Same-origin requests with the session cookie; the CSRF token (from /auth/login or
 *   /auth/session) is attached to every non-GET request.
 * - RFC 9457 problem+json responses become `ApiError` with the server's stable `code`.
 * - A 401 from a data endpoint means the session ended: the registered handler clears state
 *   and the router sends the user to sign in.
 */

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly fields: FieldError[];
  readonly requestId: string | undefined;

  constructor(
    status: number,
    code: string,
    detail: string,
    fields: FieldError[] = [],
    requestId?: string,
  ) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.fields = fields;
    this.requestId = requestId;
  }
}

export const API_BASE = "/api/v1";
const NETWORK_MESSAGE = "Clario can't be reached right now. Check your connection and try again.";
const AUTH_PATHS = new Set(["/auth/session", "/auth/login"]);

let csrfToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

export async function apiFetch<T>(
  path: string,
  { method = "GET", body, signal }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  let response: Response;
  try {
    // eslint-disable-next-line no-restricted-globals -- the one sanctioned HTTP entry point
    response = await fetch(`${API_BASE}${path}`, {
      method,
      credentials: "same-origin",
      headers,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      ...(signal ? { signal } : {}),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "network_error", NETWORK_MESSAGE);
  }

  if (response.status === 204) return undefined as T;
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const problem = (payload ?? {}) as Partial<{
      code: string;
      detail: string;
      errors: FieldError[];
      request_id: string;
    }>;
    const error = new ApiError(
      response.status,
      problem.code ?? `http_${response.status}`,
      problem.detail ?? "Something went wrong. Try again.",
      problem.errors ?? [],
      problem.request_id,
    );
    if (response.status === 401 && !AUTH_PATHS.has(path)) onUnauthorized?.();
    throw error;
  }
  return payload as T;
}
