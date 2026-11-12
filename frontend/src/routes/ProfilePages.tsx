import { Navigate, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageLoader } from "@/components/common/PageLoader";
import { DeleteAccountSection } from "@/features/auth/components/DeleteAccountSection";
import { SessionList } from "@/features/auth/components/SessionList";
import { AvatarSection } from "@/features/profile/components/AvatarSection";
import { OnboardingForm } from "@/features/profile/components/OnboardingForm";
import { PhoneSection } from "@/features/profile/components/PhoneSection";
import { PresenceSelector } from "@/features/profile/components/PresenceSelector";
import { PrivacySection } from "@/features/profile/components/PrivacySection";
import { ProfileForm } from "@/features/profile/components/ProfileForm";
import { useMe } from "@/features/profile/hooks/useProfile";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";

function useProfileOrState() {
  const me = useMe();
  if (me.isPending) return { node: <PageLoader label="Loading your profile" />, profile: null };
  if (me.isError) {
    const friendly = toUserFacingError(me.error);
    return {
      node: (
        <ErrorState
          kind={friendly.kind}
          message={friendly.message}
          requestId={friendly.requestId}
          onRetry={() => void me.refetch()}
        />
      ),
      profile: null,
    };
  }
  return { node: null, profile: me.data };
}

/** Profile setup page (FR-AUTH-015). */
export function ProfileSetupPage() {
  const navigate = useNavigate();
  const { node, profile } = useProfileOrState();
  if (!profile) return node;
  if (profile.onboarding_completed) return <Navigate to={paths.home} replace />;
  return (
    <OnboardingForm profile={profile} onDone={() => navigate(paths.home, { replace: true })} />
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section
      aria-labelledby={id}
      className="space-y-3 rounded-panel border border-border bg-surface p-4"
    >
      <h2 id={id} className="text-lg font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

/** Profile settings page: profile, photo, status, mobile number, sessions, deletion. */
export function ProfileSettingsPage() {
  const navigate = useNavigate();
  const { node, profile } = useProfileOrState();
  if (!profile) return node;
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold">Settings</h1>
      <Section id="photo-heading" title="Profile photo">
        <AvatarSection profile={profile} />
      </Section>
      <Section id="profile-heading" title="Profile">
        <ProfileForm profile={profile} />
      </Section>
      <Section id="presence-heading" title="Status">
        <PresenceSelector profile={profile} />
      </Section>
      <Section id="privacy-heading" title="Privacy and discovery">
        <PrivacySection />
      </Section>
      <Section id="phone-heading" title="Mobile number">
        <PhoneSection />
      </Section>
      <Section id="sessions-heading" title="Where you are signed in">
        <SessionList />
      </Section>
      <Section id="danger-heading" title="Delete account">
        <DeleteAccountSection onDeleted={() => navigate(paths.signIn, { replace: true })} />
      </Section>
    </div>
  );
}
