import { useEffect, useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { apiClient } from "@/lib/api/client";
import { sessionStore } from "@/lib/auth/session";
import { appRoutes } from "@/routes";

// Requests carry the in-memory token and retry once after a refresh.
sessionStore.attach(apiClient);

export function App() {
  const [router] = useState(() => createBrowserRouter(appRoutes));

  useEffect(() => {
    // Restore the session from the httpOnly refresh cookie (no token is ever persisted).
    if (sessionStore.getSnapshot().status === "unknown") void sessionStore.refresh();
  }, []);

  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
