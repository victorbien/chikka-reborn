import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRegister } from "@/features/auth/hooks/useAuth";
import { registerSchema, type RegisterInput, type RegisterValues } from "@/features/auth/schemas";
import { toUserFacingError } from "@/lib/error-handling";
import {
  applyServerFieldErrors,
  formatWait,
  hasFieldProblems,
  retryAfterSeconds,
} from "@/lib/forms";
import { paths } from "@/lib/paths";

export interface RegisterFormProps {
  onRegistered: (email: string) => void;
}

export function RegisterForm({ onRegistered }: RegisterFormProps) {
  const register = useRegister();
  const form = useForm<RegisterInput, unknown, RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: "", display_name: "", password: "", accept_terms: false },
  });
  const { errors } = form.formState;

  const onSubmit = form.handleSubmit((values) =>
    register.mutate(values, {
      onSuccess: () => onRegistered(values.email),
      onError: (error) =>
        applyServerFieldErrors(error, form.setError, [
          "email",
          "display_name",
          "password",
          "accept_terms",
        ]),
    }),
  );

  const wait = retryAfterSeconds(register.error);
  const failure = register.error ? toUserFacingError(register.error) : null;

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4" aria-labelledby="register-heading">
      <h1 id="register-heading" className="text-xl font-semibold">
        Create your account
      </h1>
      {failure && !hasFieldProblems(register.error) ? (
        <FormAlert tone="error" requestId={failure.requestId}>
          {wait
            ? `Too many sign-ups from this network. Try again in ${formatWait(wait)}.`
            : failure.message}
        </FormAlert>
      ) : null}
      <FormField label="Email" error={errors.email?.message}>
        <Input type="email" autoComplete="email" inputMode="email" {...form.register("email")} />
      </FormField>
      <FormField
        label="Display name"
        error={errors.display_name?.message}
        hint="Shown to your contacts."
      >
        <Input autoComplete="name" {...form.register("display_name")} />
      </FormField>
      <FormField
        label="Password"
        error={errors.password?.message}
        hint="At least 8 characters with an uppercase letter, a lowercase letter and a digit."
      >
        <Input type="password" autoComplete="new-password" {...form.register("password")} />
      </FormField>
      <div className="flex flex-col gap-1">
        <label className="flex min-h-11 items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1 size-5"
            aria-invalid={errors.accept_terms ? true : undefined}
            aria-describedby={errors.accept_terms ? "terms-error" : undefined}
            {...form.register("accept_terms")}
          />
          <span>I accept the Terms of Service and the Privacy Notice.</span>
        </label>
        {errors.accept_terms ? (
          <p id="terms-error" className="text-xs text-danger">
            {errors.accept_terms.message}
          </p>
        ) : null}
      </div>
      <Button type="submit" className="w-full" disabled={register.isPending}>
        {register.isPending ? "Creating account…" : "Create account"}
      </Button>
      <p className="text-center text-sm text-fg-muted">
        Already have an account?{" "}
        <Link to={paths.signIn} className="text-accent underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
