import type { ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { MainNav, type NavItem } from "@/components/navigation/MainNav";
import { Logo } from "@/components/shared/Logo";
import { paths } from "@/lib/paths";
import { useDisplayMode } from "@/lib/display-mode";
import { cn } from "@/lib/utils";

export interface AppLayoutProps {
  navItems?: readonly NavItem[];
  /** Right side of the header, e.g. the signed-in user and a sign-out button. */
  headerActions?: ReactNode;
}

/** Main application layout. Classic and Modern share the routes and the content; the shell differs. */
export function AppLayout({ navItems, headerActions }: AppLayoutProps) {
  const { mode } = useDisplayMode();
  const { pathname } = useLocation();
  const classic = mode === "classic";
  // The messenger uses the full width in Modern mode (three columns on desktop).
  const wide = !classic && pathname.startsWith(paths.messages);

  return (
    <div className="flex min-h-screen flex-col">
      <header
        className={cn(
          "border-b border-border",
          classic ? "bg-surface-raised bevel" : "sticky top-0 z-30 bg-surface",
        )}
      >
        <div
          className={cn(
            "mx-auto flex flex-wrap items-center gap-x-4 gap-y-1",
            classic ? "max-w-4xl px-2 py-1" : "max-w-5xl p-2",
          )}
        >
          {classic ? (
            <span className="flex items-center gap-2 text-sm font-bold">
              <Logo size="sm" decorative />
              Chikka Reborn · Classic
            </span>
          ) : (
            <Logo size="md" />
          )}
          {/* Small screens: logo + actions on row one, navigation scrolls on row two.
              Large screens: one row with the actions pushed to the right. */}
          <MainNav
            items={navItems}
            compact={classic}
            className="order-3 -mx-2 w-full min-w-0 overflow-x-auto px-2 lg:order-2 lg:mx-0 lg:w-auto lg:flex-1 lg:px-0"
          />
          {headerActions ? (
            <div className="order-2 ml-auto flex items-center gap-2 lg:order-3">
              {headerActions}
            </div>
          ) : null}
        </div>
      </header>
      <main
        id="main-content"
        tabIndex={-1}
        className={cn(
          "mx-auto w-full flex-1",
          classic ? "max-w-4xl p-2" : wide ? "max-w-[90rem] p-4" : "max-w-5xl p-4",
        )}
      >
        <Outlet />
      </main>
      <footer className="border-t border-border p-4 text-center text-xs text-fg-muted">
        Independent, Chikka-inspired project. Not affiliated with the original service.
      </footer>
    </div>
  );
}
