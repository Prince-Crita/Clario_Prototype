import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  ALPHA,
  ALPHA_DETAIL,
  BETA,
  expectNoA11yViolations,
  mockApi,
  renderApp,
  session,
  SIGNED_OUT,
} from "../test/harness";

const MEMBERS = {
  members: [
    { user_id: "u-1", email: "prince@crita.in", full_name: "Prince M", role: "owner" },
    { user_id: "u-2", email: "viewer@alpha.in", full_name: "Asha Viewer", role: "viewer" },
  ],
};

describe("sign in", () => {
  it("sends signed-out visitors to sign in, remembering where they were going", async () => {
    mockApi({ "GET /auth/session": SIGNED_OUT });
    const { router, container } = renderApp("/w/alpha-traders/settings");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.search).toBe("?next=%2Fw%2Falpha-traders%2Fsettings");
    expect(screen.getByRole("img", { name: "Clario" })).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("validates required fields before calling the API", async () => {
    const calls = mockApi({ "GET /auth/session": SIGNED_OUT });
    const { user } = renderApp("/login");
    await user.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });

  it("shows the server's message for wrong credentials", async () => {
    mockApi({
      "GET /auth/session": SIGNED_OUT,
      "POST /auth/login": {
        status: 401,
        body: { code: "auth.invalid_credentials", detail: "Incorrect email or password." },
      },
    });
    const { user } = renderApp("/login");
    await user.type(await screen.findByLabelText("Email"), "prince@crita.in");
    await user.type(screen.getByLabelText("Password"), "not the password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  });

  it("signs in and returns to the requested page", async () => {
    const calls = mockApi({
      "GET /auth/session": SIGNED_OUT,
      "POST /auth/login": { status: 200, body: session() },
      [`GET /workspaces/${ALPHA.id}`]: { status: 200, body: ALPHA_DETAIL },
    });
    const { user, router } = renderApp("/login?next=%2Fw%2Falpha-traders");
    await user.type(await screen.findByLabelText("Email"), "prince@crita.in");
    await user.type(screen.getByLabelText("Password"), "correct horse battery");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Alpha Traders" }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/w/alpha-traders");
    expect(calls.find((c) => c.path === "/auth/login")?.body).toEqual({
      email: "prince@crita.in",
      password: "correct horse battery",
    });
  });

  it("rejects off-site ?next= redirects", async () => {
    mockApi({
      "GET /auth/session": SIGNED_OUT,
      "POST /auth/login": { status: 200, body: session([ALPHA, BETA]) },
    });
    const { user, router } = renderApp("/login?next=%2F%2Fevil.example");
    await user.type(await screen.findByLabelText("Email"), "prince@crita.in");
    await user.type(screen.getByLabelText("Password"), "correct horse battery");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/w"));
  });
});

describe("workspaces", () => {
  it("skips the chooser when there is exactly one workspace", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session([ALPHA]) },
      [`GET /workspaces/${ALPHA.id}`]: { status: 200, body: ALPHA_DETAIL },
    });
    const { router } = renderApp("/w");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Alpha Traders" }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/w/alpha-traders");
  });

  it("lists several workspaces as rows and opens the chosen one", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session([ALPHA, BETA]) },
      [`GET /workspaces/${BETA.id}`]: { status: 200, body: { ...ALPHA_DETAIL, ...BETA } },
    });
    const { user, container } = renderApp("/w");
    const list = await screen.findByRole("list");
    expect(
      within(list)
        .getAllByRole("link")
        .map((a) => a.textContent),
    ).toEqual([expect.stringContaining("Alpha Traders"), expect.stringContaining("Beta Foods")]);
    await expectNoA11yViolations(container);
    await user.click(within(list).getByRole("link", { name: /Beta Foods/ }));
    expect(
      await screen.findByRole("heading", { level: 1, name: "Beta Foods" }),
    ).toBeInTheDocument();
  });

  it("explains what to do when the user has no workspace", async () => {
    mockApi({ "GET /auth/session": { status: 200, body: session([]) } });
    renderApp("/w");
    expect(
      await screen.findByText("You don't have access to a workspace yet."),
    ).toBeInTheDocument();
  });

  it("shows the workspace home inside the shell", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session([ALPHA, BETA]) },
      [`GET /workspaces/${ALPHA.id}`]: { status: 200, body: ALPHA_DETAIL },
    });
    const { container } = renderApp("/w/alpha-traders");
    expect(await screen.findByText("Financial year April–March")).toBeInTheDocument();
    expect(screen.getByText("Your role: Owner")).toBeInTheDocument();
    expect(screen.getByText("India Standard Time")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Connected systems" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
    await expectNoA11yViolations(container);
  });

  it("says 'not found' for a workspace the user cannot access", async () => {
    mockApi({ "GET /auth/session": { status: 200, body: session([ALPHA]) } });
    renderApp("/w/someone-elses-company");
    expect(await screen.findByRole("heading", { name: "Workspace not found" })).toBeInTheDocument();
  });

  it("switches workspace from the switcher menu", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session([ALPHA, BETA]) },
      [`GET /workspaces/${ALPHA.id}`]: { status: 200, body: ALPHA_DETAIL },
      [`GET /workspaces/${BETA.id}`]: { status: 200, body: { ...ALPHA_DETAIL, ...BETA } },
    });
    const { user, router } = renderApp("/w/alpha-traders");
    await user.click(await screen.findByRole("button", { name: /Switch workspace/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Beta Foods" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/w/beta-foods"));
  });
});

describe("settings and session", () => {
  it("lists members in a table", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET /workspaces/${ALPHA.id}/members`]: { status: 200, body: MEMBERS },
    });
    const { container } = renderApp("/w/alpha-traders/settings");
    const table = await screen.findByRole("table", { name: "Members of Alpha Traders" });
    expect(within(table).getByRole("rowheader", { name: "Asha Viewer" })).toBeInTheDocument();
    expect(within(table).getByText("Viewer")).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("changes the password with the CSRF token and confirms", async () => {
    const calls = mockApi({
      "GET /auth/session": { status: 200, body: session() },
      "POST /auth/password": { status: 204 },
    });
    const { user } = renderApp("/w/alpha-traders/settings?tab=account");
    await user.type(await screen.findByLabelText("Current password"), "old passphrase 1");
    await user.type(screen.getByLabelText("New password"), "a brand new passphrase");
    await user.type(screen.getByLabelText("Repeat new password"), "a different passphrase");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText("The passwords don't match.")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Repeat new password"));
    await user.type(screen.getByLabelText("Repeat new password"), "a brand new passphrase");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText(/Password changed/)).toBeInTheDocument();
    const post = calls.find((c) => c.path === "/auth/password");
    expect(post?.headers["X-CSRF-Token"]).toBe("csrf-token-123");
    expect(post?.body).toEqual({
      current_password: "old passphrase 1",
      new_password: "a brand new passphrase",
    });
  });

  it("maps a wrong current password to that field", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      "POST /auth/password": {
        status: 422,
        body: { code: "auth.wrong_password", detail: "Your current password is incorrect." },
      },
    });
    const { user } = renderApp("/w/alpha-traders/settings?tab=account");
    await user.type(await screen.findByLabelText("Current password"), "wrong wrong wrong");
    await user.type(screen.getByLabelText("New password"), "a brand new passphrase");
    await user.type(screen.getByLabelText("Repeat new password"), "a brand new passphrase");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText("Your current password is incorrect.")).toBeInTheDocument();
    expect(screen.getByLabelText("Current password")).toHaveAttribute("aria-invalid", "true");
  });

  it("signs out from the user menu with the CSRF token", async () => {
    const calls = mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET /workspaces/${ALPHA.id}`]: { status: 200, body: ALPHA_DETAIL },
      "POST /auth/logout": { status: 204 },
    });
    const { user, router } = renderApp("/w/alpha-traders");
    await user.click(await screen.findByRole("button", { name: /Account: prince@crita.in/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Sign out" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(calls.find((c) => c.path === "/auth/logout")?.headers["X-CSRF-Token"]).toBe(
      "csrf-token-123",
    );
  });

  it("returns to sign in when the session expires mid-use", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: session() },
      [`GET /workspaces/${ALPHA.id}/members`]: {
        status: 401,
        body: { code: "auth.session_expired", detail: "Your session has ended." },
      },
    });
    const { router } = renderApp("/w/alpha-traders/settings");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });
});
