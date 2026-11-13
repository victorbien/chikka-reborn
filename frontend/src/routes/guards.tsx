import { useEffect } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Avatar } from "@/components/shared/Avatar";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageLoader } from "@/components/common/PageLoader";
import { AppLayout } from "@/components/layout/AppLayout";
import { ADMIN_NAV_ITEMS, MAIN_NAV_ITEMS, PUBLIC_NAV_ITEMS } from "@/components/navigation/MainNav";
import { SignOutButton } from "@/features/auth/components/SignOutButton";
import { ChatRealtimeBridge } from "@/features/chat/components/ChatRealtimeBridge";
import { usePresence } from "@/features/profile/hooks/usePresenceHeartbeat";
import { useMe } from "@/features/profile/hooks/useProfile";
import { useSession } from "@/lib/auth/session";
import { useDisplayMode } from "@/lib/display-mode";
import { RealtimeProvider } from "@/lib/realtime/provider";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";

export interface RedirectState {
  from?: string;
}

/** Only same-app paths are followed after sign-in (no open redirects, no protocol tricks). */
export function safeRedirectTarget(state: unknown): string {
  const from = (state as RedirectState | null)?.from;
  if (
    typeof from !== "string" ||
    !from.startsWith("/") ||
    from.startsWith("//") ||
    from.includes("\\")
  ) {
    return paths.home;
  }
  return from;
}

/** Signed-in users only. Unknown session (restoring from the cookie) shows a loader. */
export function RequireAuth() {
  const session = useSession();
  const location = useLocation();
  if (session.status === "unknown") return <PageLoader label="Restoring your session" />;
  if (session.status === "signed-out") {
    const state: RedirectState = { from: location.pathname + location.search };
    return <Navigate to={paths.signIn} replace state={state} />;
  }
  return <Outlet />;
}

/** Profile must exist; onboarding (username) must be finished before the app (FR-AUTH-015 AC2). */
export function RequireOnboarded() {
  const me = useMe();
  if (me.isPending) return <PageLoader label="Loading your profile" />;
  if (me.isError) {
    const friendly = toUserFacingError(me.error);
    return (
      <ErrorState
        kind={friendly.kind}
        message={friendly.message}
        requestId={friendly.requestId}
        onRetry={() => void me.refetch()}
      />
    );
  }
  if (!me.data.onboarding_completed) return <Navigate to={paths.onboarding} replace />;
  return <Outlet />;
}

/** Sign-in and sign-up pages send signed-in users onward. */
export function RedirectIfSignedIn() {
  const session = useSession();
  const location = useLocation();
  if (session.status === "unknown") return <PageLoader label="Restoring your session" />;
  if (session.status === "signed-in") {
    return <Navigate to={safeRedirectTarget(location.state)} replace />;
  }
  return <Outlet />;
}

/** The signed-in shell: header with the user, presence heartbeat, display mode from the profile. */
export function SignedInAppLayout() {
  const me = useMe();
  const navigate = useNavigate();
  const { setMode } = useDisplayMode();
  usePresence(me.data?.status === "active");

  const uiMode = me.data?.ui_mode;
  useEffect(() => {
    if (uiMode) setMode(uiMode);
  }, [uiMode, setMode]);

  return (
    // One real-time connection for the whole signed-in app (active accounts only).
    <RealtimeProvider enabled={me.data?.status === "active" && me.data.onboarding_completed}>
      <ChatRealtimeBridge />
      <AppLayout
        navItems={
          me.data?.role === "admin" ? [...MAIN_NAV_ITEMS, ...ADMIN_NAV_ITEMS] : MAIN_NAV_ITEMS
        }
        headerActions={
          me.data ? (
            <>
              <span className="flex items-center gap-2 text-sm">
                <Avatar
                  name={me.data.display_name}
                  imageUrl={me.data.avatar_url ?? undefined}
                  size="sm"
                />
                <span className="hidden sm:inline">{me.data.display_name}</span>
              </span>
              <SignOutButton onSignedOut={() => navigate(paths.signIn, { replace: true })} />
            </>
          ) : null
        }
      />
    </RealtimeProvider>
  );
}

/** Public pages (style guide) adapt the navigation to the session. */
export function PublicAppLayout() {
  const session = useSession();
  return (
    <AppLayout navItems={session.status === "signed-in" ? MAIN_NAV_ITEMS : PUBLIC_NAV_ITEMS} />
  );
}
