import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLogin } from "@/features/auth/hooks/useAuth";
import { loginSchema, type LoginInput, type LoginValues } from "@/features/auth/schemas";
import { isApiError } from "@/lib/api/errors";
import { toUserFacingError } from "@/lib/error-handling";
import { formatWait, retryAfterSeconds } from "@/lib/forms";
import { paths } from "@/lib/paths";

export interface LoginFormProps {
  onSignedIn: () => void;
}

function LoginError({ error, email }: { error: unknown; email: string }) {
  const wait = retryAfterSeconds(error);
  if (wait) {
    return (
      <FormAlert tone="error">
        Too many sign-in attempts. Try again in {formatWait(wait)}, or{" "}
        <Link to={paths.forgotPassword} className="underline">
          reset your password
        </Link>
        .
      </FormAlert>
    );
  }
  if (isApiError(error) && error.code === "email_not_verified") {
    return (
      <FormAlert tone="error">
        Confirm your email address first.{" "}
        <Link to={paths.verifyEmail} state={{ email }} className="underline">
          Send a new confirmation link
        </Link>
        .
      </FormAlert>
    );
  }
  if (isApiError(error) && error.code === "invalid_credentials") {
    return <FormAlert tone="error">Email or password is incorrect.</FormAlert>;
  }
  const friendly = toUserFacingError(error);
  // 403 account_unavailable carries a safe message; toUserFacingError would replace it.
  const message =
    isApiError(error) && error.code === "account_unavailable" ? error.message : friendly.message;
  return (
    <FormAlert tone="error" requestId={friendly.requestId}>
      {message}
    </FormAlert>
  );
}

export function LoginForm({ onSignedIn }: LoginFormProps) {
  const login = useLogin();
  const form = useForm<LoginInput, unknown, LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const { errors } = form.formState;

  const onSubmit = form.handleSubmit((values) =>
    login.mutate(values, {
      onSuccess: onSignedIn,
      // Never keep a failed password in the form.
      onError: () => form.resetField("password"),
    }),
  );

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4" aria-labelledby="login-heading">
      <h1 id="login-heading" className="text-xl font-semibold">
        Sign in
      </h1>
      {login.error ? <LoginError error={login.error} email={form.getValues("email")} /> : null}
      <FormField label="Email" error={errors.email?.message}>
        <Input type="email" autoComplete="email" inputMode="email" {...form.register("email")} />
      </FormField>
      <FormField label="Password" error={errors.password?.message}>
        <Input type="password" autoComplete="current-password" {...form.register("password")} />
      </FormField>
      <Button type="submit" className="w-full" disabled={login.isPending}>
        {login.isPending ? "Signing in…" : "Sign in"}
      </Button>
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        <Link to={paths.forgotPassword} className="text-accent underline">
          Forgot password?
        </Link>
        <Link to={paths.register} className="text-accent underline">
          Create an account
        </Link>
      </div>
    </form>
  );
}
