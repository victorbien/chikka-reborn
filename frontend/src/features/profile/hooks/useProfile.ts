import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { profileApi } from "@/features/profile/api";
import { profileKeys } from "@/features/profile/query-keys";
import type { OnboardingValues, ProfileFormValues } from "@/features/profile/schemas";
import type { PresencePreference, Profile } from "@/features/profile/types";

export function useMe(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: profileKeys.me(),
    queryFn: ({ signal }) => profileApi.getMe(signal),
    enabled: options.enabled ?? true,
  });
}

/** Mutations that return the profile write it straight into the cache (no refetch). */
function useSetMe() {
  const queryClient = useQueryClient();
  return (profile: Profile) => queryClient.setQueryData(profileKeys.me(), profile);
}

export function useUpdateProfile() {
  const setMe = useSetMe();
  return useMutation({
    mutationFn: (changes: Partial<ProfileFormValues>) => profileApi.updateMe(changes),
    onSuccess: setMe,
  });
}

export function useCompleteOnboarding() {
  const setMe = useSetMe();
  return useMutation({
    mutationFn: (values: OnboardingValues) => profileApi.completeOnboarding(values),
    onSuccess: setMe,
  });
}

export function useUploadAvatar() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => profileApi.uploadAvatar(file),
    onSuccess: ({ avatar_url }) =>
      queryClient.setQueryData<Profile>(profileKeys.me(), (current) =>
        current ? { ...current, avatar_url } : current,
      ),
  });
}

export function useRemoveAvatar() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => profileApi.removeAvatar(),
    onSuccess: () =>
      queryClient.setQueryData<Profile>(profileKeys.me(), (current) =>
        current ? { ...current, avatar_url: null } : current,
      ),
  });
}

export function useSetPresence() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (preference: PresencePreference) => profileApi.setPresence(preference),
    onSuccess: (presence) => {
      queryClient.setQueryData(profileKeys.presence(), presence);
      queryClient.setQueryData<Profile>(profileKeys.me(), (current) =>
        current ? { ...current, presence_preference: presence.preference } : current,
      );
    },
  });
}
