import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type { OnboardingValues, ProfileFormValues } from "@/features/profile/schemas";
import type {
  PhoneStart,
  PhoneStatus,
  PresenceInfo,
  PresencePreference,
  PrivacySettings,
  Profile,
  SimulatedSms,
} from "@/features/profile/types";

const ME = "/api/v1/users/me";

export function createProfileApi(client: ApiClient = apiClient) {
  return {
    getMe: (signal?: AbortSignal) => client.get<Envelope<Profile>>(ME, { signal }).then(unwrap),
    updateMe: (changes: Partial<ProfileFormValues>) =>
      client.patch<Envelope<Profile>>(ME, changes).then(unwrap),
    completeOnboarding: (values: OnboardingValues) =>
      client.post<Envelope<Profile>>(`${ME}/onboarding`, values).then(unwrap),
    uploadAvatar: (file: File) => {
      const form = new FormData();
      form.append("avatar", file);
      return client
        .post<Envelope<{ avatar_url: string | null }>>(`${ME}/avatar`, form)
        .then(unwrap);
    },
    getPrivacy: (signal?: AbortSignal) =>
      client.get<Envelope<PrivacySettings>>(`${ME}/privacy`, { signal }).then(unwrap),
    updatePrivacy: (changes: Partial<PrivacySettings>) =>
      client.patch<Envelope<PrivacySettings>>(`${ME}/privacy`, changes).then(unwrap),
    removeAvatar: () => client.delete<void>(`${ME}/avatar`),
    setPresence: (preference: PresencePreference) =>
      client.put<Envelope<PresenceInfo>>(`${ME}/presence`, { preference }).then(unwrap),
    heartbeat: (idle: boolean) =>
      client.post<Envelope<PresenceInfo>>(`${ME}/presence/heartbeat`, { idle }).then(unwrap),
    phoneStatus: () => client.get<Envelope<PhoneStatus>>(`${ME}/phone`).then(unwrap),
    startPhone: (phoneNumber: string, password?: string) =>
      client
        .post<Envelope<PhoneStart>>(`${ME}/phone`, {
          phone_number: phoneNumber,
          ...(password ? { password } : {}),
        })
        .then(unwrap),
    confirmPhone: (phoneNumber: string, code: string) =>
      client
        .post<Envelope<PhoneStatus>>(`${ME}/phone/verify`, { phone_number: phoneNumber, code })
        .then(unwrap),
    removePhone: (password: string) => client.delete<void>(`${ME}/phone`, { password }),
    simulatedInbox: () =>
      client.get<Envelope<SimulatedSms[]>>(`${ME}/phone/simulated-inbox`).then(unwrap),
  };
}

export const profileApi = createProfileApi();
