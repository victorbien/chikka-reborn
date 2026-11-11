import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type { TokenData } from "@/lib/auth/session";
import type { LoginValues, RegisterValues } from "@/features/auth/schemas";

export interface MessageData {
  message: string;
}

export interface SessionInfo {
  id: string;
  created_at: string;
  last_active_at: string | null;
  device: string;
  ip_prefix: string | null;
  current: boolean;
}

const AUTH = "/api/v1/auth";
// Auth endpoints answer 401 for wrong credentials; that must never trigger a token refresh.
const NO_REFRESH = { skipAuthRefresh: true } as const;

export function createAuthApi(client: ApiClient = apiClient) {
  return {
    register: (values: RegisterValues) =>
      client.post<Envelope<MessageData>>(`${AUTH}/register`, values, NO_REFRESH).then(unwrap),
    login: (values: LoginValues) =>
      client.post<Envelope<TokenData>>(`${AUTH}/login`, values, NO_REFRESH).then(unwrap),
    logout: (scope: "local" | "global") => client.post<void>(`${AUTH}/logout`, { scope }),
    verifyEmail: (tokenHash: string) =>
      client
        .post<Envelope<TokenData>>(`${AUTH}/verify-email`, { token_hash: tokenHash }, NO_REFRESH)
        .then(unwrap),
    resendVerification: (email: string) =>
      client
        .post<Envelope<MessageData>>(`${AUTH}/resend-verification`, { email }, NO_REFRESH)
        .then(unwrap),
    requestPasswordReset: (email: string) =>
      client
        .post<Envelope<MessageData>>(`${AUTH}/reset-password`, { email }, NO_REFRESH)
        .then(unwrap),
    confirmPasswordReset: (tokenHash: string, newPassword: string, confirmPassword: string) =>
      client
        .post<Envelope<MessageData>>(
          `${AUTH}/reset-password/confirm`,
          { token_hash: tokenHash, new_password: newPassword, confirm_password: confirmPassword },
          NO_REFRESH,
        )
        .then(unwrap),
    listSessions: () => client.get<Envelope<SessionInfo[]>>(`${AUTH}/sessions`).then(unwrap),
    revokeSession: (id: string) =>
      client.delete<void>(`${AUTH}/sessions/${encodeURIComponent(id)}`),
    revokeOtherSessions: () =>
      client.post<Envelope<MessageData>>(`${AUTH}/sessions/revoke-others`).then(unwrap),
    deleteAccount: (password: string) =>
      client
        .delete<Envelope<{ message: string; deleted_at: string }>>("/api/v1/users/me", {
          password,
          confirmation: "DELETE",
        })
        .then(unwrap),
  };
}

export const authApi = createAuthApi();
