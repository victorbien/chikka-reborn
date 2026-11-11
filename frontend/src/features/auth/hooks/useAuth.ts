import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/features/auth/api";
import { authKeys } from "@/features/auth/query-keys";
import type { LoginValues, RegisterValues } from "@/features/auth/schemas";
import { sessionStore, type TokenData } from "@/lib/auth/session";

/** Sign-in-producing mutations hand the token to the in-memory session store. */
function useSignedIn() {
  const queryClient = useQueryClient();
  return (tokens: TokenData) => {
    // A different account may have been signed in on this tab; drop its cached data.
    queryClient.clear();
    sessionStore.signIn(tokens);
  };
}

export function useRegister() {
  return useMutation({ mutationFn: (values: RegisterValues) => authApi.register(values) });
}

export function useLogin() {
  const signedIn = useSignedIn();
  return useMutation({
    mutationFn: (values: LoginValues) => authApi.login(values),
    onSuccess: signedIn,
  });
}

export function useVerifyEmail() {
  const signedIn = useSignedIn();
  return useMutation({
    mutationFn: (tokenHash: string) => authApi.verifyEmail(tokenHash),
    onSuccess: signedIn,
  });
}

export function useResendVerification() {
  return useMutation({ mutationFn: (email: string) => authApi.resendVerification(email) });
}

export function useRequestPasswordReset() {
  return useMutation({ mutationFn: (email: string) => authApi.requestPasswordReset(email) });
}

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: (input: { tokenHash: string; newPassword: string; confirmPassword: string }) =>
      authApi.confirmPasswordReset(input.tokenHash, input.newPassword, input.confirmPassword),
  });
}

/** Signs out locally even if the server is unreachable (FR-AUTH-010 alternative A). */
export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (scope: "local" | "global" = "local") => {
      try {
        await authApi.logout(scope);
      } catch {
        // The local session still ends; the server session expires or is revoked later.
      }
    },
    onSettled: () => {
      sessionStore.signOut();
      queryClient.clear();
    },
  });
}

export function useSessions() {
  return useQuery({ queryKey: authKeys.sessions(), queryFn: () => authApi.listSessions() });
}

export function useRevokeSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => authApi.revokeSession(id),
    onSettled: () => queryClient.invalidateQueries({ queryKey: authKeys.sessions() }),
  });
}

export function useRevokeOtherSessions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => authApi.revokeOtherSessions(),
    onSettled: () => queryClient.invalidateQueries({ queryKey: authKeys.sessions() }),
  });
}

export function useDeleteAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => authApi.deleteAccount(password),
    onSuccess: () => {
      sessionStore.signOut();
      queryClient.clear();
    },
  });
}
