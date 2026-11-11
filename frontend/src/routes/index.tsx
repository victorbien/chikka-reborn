import type { RouteObject } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { RootLayout } from "@/components/layout/RootLayout";
import { HomePage } from "@/routes/HomePage";
import { NotFoundPage } from "@/routes/NotFoundPage";
import { RouteErrorPage } from "@/routes/RouteErrorPage";
import { SignInPlaceholderPage } from "@/routes/SignInPlaceholderPage";
import { StyleGuide } from "@/routes/StyleGuide";

export const appRoutes: RouteObject[] = [
  {
    element: <RootLayout />,
    errorElement: <RouteErrorPage />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "style-guide", element: <StyleGuide /> },
        ],
      },
      {
        path: "auth",
        element: <AuthLayout />,
        children: [{ path: "sign-in", element: <SignInPlaceholderPage /> }],
      },
      { path: "*", element: <AppLayout />, children: [{ path: "*", element: <NotFoundPage /> }] },
    ],
  },
];
