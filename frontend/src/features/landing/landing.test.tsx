import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { GHOST_QUIPS } from "@/features/landing/components/GhostMascot";
import { HISTORY, PURPOSE } from "@/features/landing/content";
import { fail, mockApi, signedInRoutes } from "@/test/api-mock";
import { renderApp } from "@/test/render-app";

const signedOut = {
  "POST /api/v1/auth/refresh": fail(401, "not_authenticated", "Please sign in."),
};

describe("landing page", () => {
  it("shows visitors the landing page at the home address", async () => {
    mockApi(signedOut);
    const { router } = renderApp("/");
    expect(
      await screen.findByRole("heading", { level: 1, name: /refused to die/i }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
    expect(screen.getAllByRole("link", { name: /^sign in$/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /create (an )?account/i })[0]).toHaveAttribute(
      "href",
      "/auth/register",
    );
  });

  it("links from the sign-in page back to the landing page", async () => {
    mockApi(signedOut);
    const { router } = renderApp("/auth/sign-in");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: "What is Chikka Reborn?" }));
    expect(router.state.location.pathname).toBe("/");
    expect(
      await screen.findByRole("heading", { level: 1, name: /refused to die/i }),
    ).toBeInTheDocument();
  });

  it("still shows the app home to a signed-in user", async () => {
    mockApi(signedInRoutes());
    renderApp("/");
    expect(await screen.findByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /refused to die/i })).not.toBeInTheDocument();
  });

  it("still redirects visitors from other protected pages to sign in", async () => {
    mockApi(signedOut);
    const { router } = renderApp("/contacts");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/auth/sign-in");
  });

  it("explains what it is, its history and its purpose", async () => {
    mockApi(signedOut);
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByRole("heading", { name: "What is Chikka Reborn?" })).toBeInTheDocument();
    for (const entry of HISTORY) {
      expect(screen.getByRole("heading", { name: entry.title })).toBeInTheDocument();
    }
    expect(screen.getByRole("heading", { name: "Why bring it back?" })).toBeInTheDocument();
    for (const entry of PURPOSE) {
      expect(screen.getByRole("heading", { name: entry.title })).toBeInTheDocument();
    }
  });

  it("labels simulated SMS and states the project is not affiliated", async () => {
    mockApi(signedOut);
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByText("SIMULATED")).toBeInTheDocument();
    expect(screen.getByText(/Honest ghost disclosure/i)).toBeInTheDocument();
    const footer = screen.getByRole("contentinfo");
    expect(within(footer).getByText(/not affiliated with or\s+endorsed by/i)).toBeInTheDocument();
  });

  it("has one h1 and a focusable main landmark for the skip link", async () => {
    mockApi(signedOut);
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
  });

  it("cycles the ghost's quips in order when poked", async () => {
    mockApi(signedOut);
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    const user = userEvent.setup();
    const ghost = screen.getByRole("button", { name: "Poke the ghost" });
    expect(screen.getByText("Psst. Poke me.")).toBeInTheDocument();

    await user.click(ghost);
    expect(screen.getByText(GHOST_QUIPS[1])).toBeInTheDocument();
    await user.click(ghost);
    expect(screen.getByText(GHOST_QUIPS[2])).toBeInTheDocument();
    expect(screen.getByText(GHOST_QUIPS[2])).toHaveAttribute("aria-live", "polite");
  });
});
