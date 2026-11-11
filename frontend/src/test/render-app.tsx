import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { StrictMode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { apiClient } from "@/lib/api/client";
import { sessionStore } from "@/lib/auth/session";
import { appRoutes } from "@/routes";

/**
 * Renders the real route tree at `path`, restoring the session the way App does on load.
 * Pair with mockApi(); the refresh route decides whether the user starts signed in.
 */
function splitPath(path: string): { pathname: string; search: string } {
  const [pathname = "/", query] = path.split("?");
  return { pathname, search: query ? `?${query}` : "" };
}

export function renderApp(path: string, options: { state?: unknown; strict?: boolean } = {}) {
  sessionStore.reset();
  sessionStore.attach(apiClient);
  void sessionStore.refresh();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(appRoutes, {
    initialEntries: [{ ...splitPath(path), state: options.state }],
  });
  const tree = (
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  );
  const view = render(options.strict ? <StrictMode>{tree}</StrictMode> : tree);
  return { ...view, router, queryClient };
}
