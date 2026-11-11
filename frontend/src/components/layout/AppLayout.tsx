import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";
import { MainNav, type NavItem } from "@/components/navigation/MainNav";

export interface AppLayoutProps {
  navItems?: readonly NavItem[];
  /** Right side of the header, e.g. the signed-in user and a sign-out button. */
  headerActions?: ReactNode;
}

/** Main application layout. */
export function AppLayout({ navItems, headerActions }: AppLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 p-2">
          <span className="text-lg font-bold">Chikka Reborn</span>
          <MainNav items={navItems} />
          {headerActions ? <div className="flex items-center gap-2">{headerActions}</div> : null}
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
