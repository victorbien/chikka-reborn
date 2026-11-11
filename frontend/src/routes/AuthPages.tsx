import { useCallback } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { FormAlert } from "@/components/common/FormAlert";
import { LoginForm } from "@/features/auth/components/LoginForm";
import { ForgotPasswordForm, ResetPasswordForm } from "@/features/auth/components/PasswordForms";
import { RegisterForm } from "@/features/auth/components/RegisterForm";
import { VerifyEmailPanel } from "@/features/auth/components/VerifyEmailPanel";
import { paths } from "@/lib/paths";
import { safeRedirectTarget } from "@/routes/guards";

export function SignInPage() {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <LoginForm onSignedIn={() => navigate(safeRedirectTarget(location.state), { replace: true })} />
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  return (
    <RegisterForm
      onRegistered={(email) => navigate(paths.verifyEmail, { replace: true, state: { email } })}
    />
  );
}

export function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const tokenHash = params.get("token_hash");
  if (!tokenHash) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Reset link missing</h1>
        <FormAlert tone="error">
          Open the link from your reset email, or request a new one.
        </FormAlert>
        <Link to={paths.forgotPassword} className="text-sm text-accent underline">
          Request a reset link
        </Link>
      </div>
    );
  }
  return <ResetPasswordForm tokenHash={tokenHash} />;
}

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const email = (location.state as { email?: string } | null)?.email ?? null;
  const onVerified = useCallback(() => navigate(paths.onboarding, { replace: true }), [navigate]);
  return (
    <VerifyEmailPanel tokenHash={params.get("token_hash")} email={email} onVerified={onVerified} />
  );
}
