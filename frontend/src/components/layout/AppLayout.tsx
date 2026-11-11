import { Outlet } from "react-router-dom";
import { MainNav } from "@/components/navigation/MainNav";

/** Main application layout for signed-in areas. */
export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 p-2">
          <span className="text-lg font-bold">Chikka Reborn</span>
          <MainNav />
        </div>
      </header>
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-5xl flex-1 p-4">
        <Outlet />
      </main>
      <footer className="border-t border-border p-4 text-center text-xs text-fg-muted">
        Independent, Chikka-inspired project. Not affiliated with the original service.
      </footer>
    </div>
  );
}
