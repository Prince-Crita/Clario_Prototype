import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, setCsrfToken, setUnauthorizedHandler } from "./api/client";
import { cx } from "./cx";
import { fiscalYearLabel, safeNext } from "./labels";

function reply(status: number, body?: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status })),
  );
}

afterEach(() => {
  setCsrfToken(null);
  setUnauthorizedHandler(null);
});

describe("apiFetch", () => {
  it("turns problem+json into ApiError with code, detail and field errors", async () => {
    reply(422, {
      code: "validation_failed",
      detail: "Some fields are not valid",
      errors: [{ field: "email", message: "Required" }],
      request_id: "req-1",
    });
    const error = await apiFetch("/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: "validation_failed", requestId: "req-1" });
    expect((error as ApiError).fields).toEqual([{ field: "email", message: "Required" }]);
  });

  it("reports network failures in plain language", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))),
    );
    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("sends the CSRF token only on writes", async () => {
    reply(200, {});
    setCsrfToken("tok");
    await apiFetch("/x");
    await apiFetch("/y", { method: "POST", body: {} });
    const mock = vi.mocked(fetch);
    expect(
      (mock.mock.calls[0]?.[1]?.headers as Record<string, string>)["X-CSRF-Token"],
    ).toBeUndefined();
    expect((mock.mock.calls[1]?.[1]?.headers as Record<string, string>)["X-CSRF-Token"]).toBe(
      "tok",
    );
  });

  it("calls the unauthorized handler for data requests but not for the session probe", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    reply(401, { code: "auth.required", detail: "Sign in" });
    await apiFetch("/auth/session").catch(() => undefined);
    expect(handler).not.toHaveBeenCalled();
    await apiFetch("/workspaces").catch(() => undefined);
    expect(handler).toHaveBeenCalledOnce();
  });

  it("returns undefined for 204", async () => {
    reply(204);
    await expect(apiFetch("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });
});

describe("labels and helpers", () => {
  it("names fiscal years", () => {
    expect(fiscalYearLabel(4)).toBe("April–March");
    expect(fiscalYearLabel(1)).toBe("January–December");
  });

  it("only allows in-app redirects", () => {
    expect(safeNext("/w/alpha")).toBe("/w/alpha");
    expect(safeNext("//evil.example")).toBe("/w");
    expect(safeNext("https://evil.example")).toBe("/w");
    expect(safeNext(null)).toBe("/w");
  });

  it("joins class names", () => {
    expect(cx("a", undefined, false, "b")).toBe("a b");
  });
});
