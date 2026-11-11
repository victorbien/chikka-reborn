import { QueryClient } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { appRoutes } from "@/routes";
import type { HealthStatus } from "@/types/api";

const HEALTH: HealthStatus = {
  status: "ok",
  service: "chikka-reborn-api",
  version: "0.1.0",
  environment: "test",
  sms_mode: "simulation",
  database: "not_configured",
  request_id: "req-1",
};

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  return render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
}

function stubFetch(response: Response | Error) {
  const fetchMock = vi.fn(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("application routes", () => {
  it("shows server status from the health endpoint on the home page", async () => {
    stubFetch(new Response(JSON.stringify(HEALTH)));
    renderAt("/");
    expect(await screen.findByText("Simulation (no real SMS)")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  });

  it("shows a readable error with a retry when the server is unreachable", async () => {
    stubFetch(new TypeError("Failed to fetch"));
    renderAt("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("You are offline");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("renders the auth layout without main navigation", () => {
    renderAt("/auth/sign-in");
    expect(screen.getByText("Sign-in is not available yet")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  });

  it("renders the style guide inside the app layout", () => {
    renderAt("/style-guide");
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Chikka Reborn" })).toBeInTheDocument();
  });

  it("renders a not-found page for unknown routes", () => {
    renderAt("/nope");
    expect(screen.getByText("Page not found")).toBeInTheDocument();
  });
});
