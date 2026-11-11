import { Outlet } from "react-router-dom";

/** Centred, navigation-free layout for sign-in, sign-up and recovery screens. */
export function AuthLayout() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4">
      <div className="text-center">
        <p className="text-2xl font-bold">Chikka Reborn</p>
        <p className="text-sm text-fg-muted">The Messenger That Refused to Die.</p>
      </div>
      <main
        id="main-content"
        tabIndex={-1}
        className="w-full max-w-sm rounded-panel border border-border bg-surface p-4 bevel"
      >
        <Outlet />
      </main>
      <p className="max-w-sm text-center text-xs text-fg-muted">
        Independent, Chikka-inspired project. Not affiliated with the original service.
      </p>
    </div>
  );
}
