import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fail, makeProfile, mockApi, signedInRoutes } from "@/test/api-mock";
import { renderApp } from "@/test/render-app";

const signedOut = {
  "POST /api/v1/auth/refresh": fail(401, "not_authenticated", "Please sign in."),
};

describe("route guards", () => {
  it("sends visitors to sign in and remembers where they were going", async () => {
    mockApi(signedOut);
    const { router } = renderApp("/settings/profile");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/auth/sign-in");
    expect(router.state.location.state).toEqual({ from: "/settings/profile" });
  });

  it("shows the app shell with server status to an onboarded user", async () => {
    mockApi(signedInRoutes());
    renderApp("/");
    expect(await screen.findByText("Simulation (no real SMS)")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("sends users without a finished profile to setup", async () => {
    mockApi(signedInRoutes(makeProfile({ onboarding_completed: false, username: null })));
    const { router } = renderApp("/");
    expect(await screen.findByRole("heading", { name: "Set up your profile" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/onboarding");
  });

  it("sends signed-in users away from the sign-in page", async () => {
    mockApi(signedInRoutes());
    const { router } = renderApp("/auth/sign-in");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });

  it("shows a readable error when the profile cannot load", async () => {
    mockApi({ ...signedInRoutes(), "GET /api/v1/users/me": fail(503, "service_unavailable") });
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("The server had a problem");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("keeps the style guide public", async () => {
    mockApi(signedOut);
    renderApp("/style-guide");
    expect(await screen.findByRole("link", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Chikka Reborn" })).toBeInTheDocument();
  });

  it("renders a not-found page for unknown routes", async () => {
    mockApi(signedOut);
    renderApp("/nope");
    expect(await screen.findByText("Page not found")).toBeInTheDocument();
  });
});
