import { Outlet } from "react-router-dom";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";

/** Global layout: skip link for keyboard users plus the routed content. */
export function RootLayout() {
  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-fg"
      >
        Skip to main content
      </a>
      <ErrorBoundary>
        <Outlet />
      </ErrorBoundary>
    </>
  );
}
