import { useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { appRoutes } from "@/routes";

export function App() {
  const [router] = useState(() => createBrowserRouter(appRoutes));
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
