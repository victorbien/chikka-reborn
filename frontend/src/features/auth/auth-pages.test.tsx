import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { sessionStore } from "@/lib/auth/session";
import { fail, mockApi, ok, signedInRoutes, TOKENS } from "@/test/api-mock";
import { renderApp } from "@/test/render-app";

const signedOut = {
  "POST /api/v1/auth/refresh": fail(401, "not_authenticated", "Please sign in."),
};
const PASSWORD = "Correct-Horse-7";

async function fillRegistration(
  user: ReturnType<typeof userEvent.setup>,
  overrides: Partial<Record<string, string>> = {},
) {
  await user.type(await screen.findByLabelText("Email"), overrides.email ?? "marites@example.com");
  await user.type(screen.getByLabelText("Display name"), overrides.name ?? "Marites Santos");
  await user.type(screen.getByLabelText("Password"), overrides.password ?? PASSWORD);
}

describe("registration", () => {
  it("validates in the browser before sending anything", async () => {
    const api = mockApi(signedOut);
    const user = userEvent.setup();
    renderApp("/auth/register");
    await fillRegistration(user, { email: "not-an-email", name: "M", password: "weakpass" });
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Use at least 2 characters.")).toBeInTheDocument();
    expect(screen.getByText("Include an uppercase letter.")).toBeInTheDocument();
    expect(
      screen.getByText("You need to accept the Terms and Privacy Notice."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(api.callsTo("POST", "/api/v1/auth/register")).toHaveLength(0);
  });

  it("registers and shows the check-your-inbox screen", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /api/v1/auth/register": {
        status: 202,
        body: { data: { message: "Check your inbox." }, request_id: "r" },
      },
    });
    const user = userEvent.setup();
    const { router } = renderApp("/auth/register");
    await fillRegistration(user, { email: "Marites@Example.com" });
    await user.click(screen.getByLabelText(/I accept the Terms/));
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Confirm your email" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/auth/verify-email");
    expect(screen.getByText("marites@example.com")).toBeInTheDocument();
    expect(api.callsTo("POST", "/api/v1/auth/register")[0]?.body).toEqual({
      email: "marites@example.com",
      display_name: "Marites Santos",
      password: PASSWORD,
      accept_terms: true,
    });
  });

  it("shows server field errors next to the field", async () => {
    mockApi({
      ...signedOut,
      "POST /api/v1/auth/register": fail(422, "weak_password", "Choose a stronger password.", {
        problems: [{ field: "body.password", reason: "Password is too weak" }],
      }),
    });
    const user = userEvent.setup();
    renderApp("/auth/register");
    await fillRegistration(user);
    await user.click(screen.getByLabelText(/I accept the Terms/));
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Password is too weak")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("sign in", () => {
  async function signIn(user: ReturnType<typeof userEvent.setup>, password = PASSWORD) {
    await user.type(await screen.findByLabelText("Email"), "marites@example.com");
    await user.type(screen.getByLabelText("Password"), password);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
  }

  it("signs in, keeps the token in memory only and returns to the requested page", async () => {
    const routes = signedInRoutes();
    const api = mockApi({ ...routes, ...signedOut, "POST /api/v1/auth/login": ok(TOKENS) });
    const user = userEvent.setup();
    const { router } = renderApp("/auth/sign-in", { state: { from: "/settings/profile" } });
    await signIn(user);

    await waitFor(() => expect(router.state.location.pathname).toBe("/settings/profile"));
    expect(sessionStore.getSnapshot()).toEqual({ status: "signed-in", accessToken: "access-1" });
    expect(window.localStorage.length).toBe(0);
    const login = api.callsTo("POST", "/api/v1/auth/login")[0];
    expect(login?.credentials).toBe("include");
    const me = api.callsTo("GET", "/api/v1/users/me")[0];
    expect(me?.headers.Authorization).toBe("Bearer access-1");
  });

  it("ignores redirect targets outside the app", async () => {
    mockApi({ ...signedInRoutes(), ...signedOut, "POST /api/v1/auth/login": ok(TOKENS) });
    const user = userEvent.setup();
    const { router } = renderApp("/auth/sign-in", { state: { from: "//evil.example/steal" } });
    await signIn(user);
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });

  it("shows one generic message for wrong credentials and clears the password", async () => {
    mockApi({
      ...signedOut,
      "POST /api/v1/auth/login": fail(
        401,
        "invalid_credentials",
        "Email or password is incorrect.",
      ),
    });
    const user = userEvent.setup();
    renderApp("/auth/sign-in");
    await signIn(user, "Wrong-Pass-1");
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(sessionStore.getSnapshot().status).toBe("signed-out");
  });

  it("explains unverified accounts and links to a new confirmation email", async () => {
    mockApi({
      ...signedOut,
      "POST /api/v1/auth/login": fail(
        403,
        "email_not_verified",
        "Confirm your email address before signing in.",
      ),
    });
    const user = userEvent.setup();
    renderApp("/auth/sign-in");
    await signIn(user);
    expect(
      await screen.findByRole("link", { name: "Send a new confirmation link" }),
    ).toBeInTheDocument();
  });

  it("shows the lockout wait time", async () => {
    mockApi({
      ...signedOut,
      "POST /api/v1/auth/login": fail(429, "rate_limited", "Too many sign-in attempts.", {
        retry_after_seconds: 840,
      }),
    });
    const user = userEvent.setup();
    renderApp("/auth/sign-in");
    await signIn(user);
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in 14 minutes");
  });
});

describe("email verification", () => {
  it("confirms the link once, signs in and continues to profile setup", async () => {
    const api = mockApi({
      ...signedInRoutes(),
      ...signedOut,
      "POST /api/v1/auth/verify-email": ok(TOKENS),
    });
    const { router } = renderApp("/auth/verify-email?token_hash=abcdefgh1234");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(api.callsTo("POST", "/api/v1/auth/verify-email")).toHaveLength(1);
    expect(api.callsTo("POST", "/api/v1/auth/verify-email")[0]?.body).toEqual({
      token_hash: "abcdefgh1234",
    });
  });

  it("does not spend a single-use link twice under StrictMode", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /api/v1/auth/verify-email": fail(
        400,
        "invalid_or_expired_link",
        "This confirmation link is invalid or has expired.",
      ),
    });
    renderApp("/auth/verify-email?token_hash=abcdefgh1234", { strict: true });
    expect(await screen.findByRole("heading", { name: "Confirmation failed" })).toBeInTheDocument();
    expect(api.callsTo("POST", "/api/v1/auth/verify-email")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Send a new link" })).toBeInTheDocument();
  });

  it("resends with a neutral confirmation", async () => {
    mockApi({
      ...signedOut,
      "POST /api/v1/auth/resend-verification": ok({
        message: "If the address needs confirming, we sent a new link.",
      }),
    });
    const user = userEvent.setup();
    renderApp("/auth/verify-email", { state: { email: "marites@example.com" } });
    expect(await screen.findByLabelText("Email")).toHaveValue("marites@example.com");
    await user.click(screen.getByRole("button", { name: "Send a new link" }));
    expect(await screen.findByRole("status")).toHaveTextContent("If the address needs confirming");
  });
});

describe("password reset", () => {
  it("answers the same way for any address", async () => {
    mockApi({
      ...signedOut,
      "POST /api/v1/auth/reset-password": ok({
        message: "If an account exists for that address, we sent a password reset link.",
      }),
    });
    const user = userEvent.setup();
    renderApp("/auth/forgot-password");
    await user.type(await screen.findByLabelText("Email"), "someone@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(await screen.findByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("If an account exists");
  });

  it("checks the passwords match before using the link", async () => {
    const api = mockApi(signedOut);
    const user = userEvent.setup();
    renderApp("/auth/reset-password?token_hash=abcdefgh1234");
    await user.type(await screen.findByLabelText("New password"), "Brand-New-Pass-2");
    await user.type(screen.getByLabelText("Confirm new password"), "Different-Pass-2");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText("Passwords do not match.")).toBeInTheDocument();
    expect(api.callsTo("POST", "/api/v1/auth/reset-password/confirm")).toHaveLength(0);
  });

  it("sets the new password and says every device was signed out", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /api/v1/auth/reset-password/confirm": ok({
        message: "Your password has been changed. Please sign in.",
      }),
    });
    const user = userEvent.setup();
    renderApp("/auth/reset-password?token_hash=abcdefgh1234");
    await user.type(await screen.findByLabelText("New password"), "Brand-New-Pass-2");
    await user.type(screen.getByLabelText("Confirm new password"), "Brand-New-Pass-2");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText(/signed out on every device/)).toBeInTheDocument();
    expect(api.callsTo("POST", "/api/v1/auth/reset-password/confirm")[0]?.body).toEqual({
      token_hash: "abcdefgh1234",
      new_password: "Brand-New-Pass-2",
      confirm_password: "Brand-New-Pass-2",
    });
  });

  it("offers a new link when the reset link has expired", async () => {
    mockApi({
      ...signedOut,
      "POST /api/v1/auth/reset-password/confirm": fail(
        400,
        "invalid_or_expired_link",
        "This reset link is invalid, expired or already used. Request a new one.",
      ),
    });
    const user = userEvent.setup();
    renderApp("/auth/reset-password?token_hash=abcdefgh1234");
    await user.type(await screen.findByLabelText("New password"), "Brand-New-Pass-2");
    await user.type(screen.getByLabelText("Confirm new password"), "Brand-New-Pass-2");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("link", { name: "Request a new link" })).toBeInTheDocument();
  });

  it("explains a missing token", async () => {
    mockApi(signedOut);
    renderApp("/auth/reset-password");
    expect(await screen.findByRole("heading", { name: "Reset link missing" })).toBeInTheDocument();
  });
});

describe("sign out", () => {
  it("clears the session even when the server cannot be reached", async () => {
    mockApi({ ...signedInRoutes(), "POST /api/v1/auth/logout": fail(503, "service_unavailable") });
    const user = userEvent.setup();
    const { router, queryClient } = renderApp("/");
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/auth/sign-in"));
    expect(sessionStore.getSnapshot().status).toBe("signed-out");
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
  });
});
