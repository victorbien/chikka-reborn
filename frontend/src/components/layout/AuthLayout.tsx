import { Link, Outlet, useLocation } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Logo } from "@/components/shared/Logo";
import { paths } from "@/lib/paths";

/** Centred, navigation-free layout for sign-in, sign-up and recovery screens. */
export function AuthLayout() {
  const { pathname } = useLocation();
  // Onboarding is for signed-in users, and "/" would send them straight back here.
  const showAboutLink = pathname !== paths.onboarding;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4">
      <div className="text-center">
        <Logo size="lg" className="mx-auto" />
        <p className="text-sm text-fg-muted">The Messenger That Refused to Die.</p>
      </div>
      <main
        id="main-content"
        tabIndex={-1}
        className="w-full max-w-sm rounded-panel border border-border bg-surface p-4 bevel"
      >
        <Outlet />
      </main>
      {showAboutLink ? (
        <Link
          to={paths.home}
          className="inline-flex min-h-11 items-center gap-1 text-sm text-accent underline"
        >
          <ArrowLeft aria-hidden className="size-4" />
          What is Chikka Reborn?
        </Link>
      ) : null}
      <p className="max-w-sm text-center text-xs text-fg-muted">
        Independent, Chikka-inspired project. Not affiliated with the original service.
      </p>
    </div>
  );
}
