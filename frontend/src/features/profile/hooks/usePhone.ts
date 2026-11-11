import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { profileApi } from "@/features/profile/api";
import { profileKeys } from "@/features/profile/query-keys";

export function usePhoneStatus() {
  return useQuery({ queryKey: profileKeys.phone(), queryFn: () => profileApi.phoneStatus() });
}

/** Simulated codes only. The endpoint answers 404 in live mode and in production. */
export function useSimulatedInbox(enabled: boolean) {
  return useQuery({
    queryKey: profileKeys.simulatedInbox(),
    queryFn: () => profileApi.simulatedInbox(),
    enabled,
    refetchInterval: enabled ? 5_000 : false,
    retry: false,
  });
}

export function useStartPhoneVerification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { phoneNumber: string; password?: string }) =>
      profileApi.startPhone(input.phoneNumber, input.password),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: profileKeys.simulatedInbox() }),
  });
}

export function useConfirmPhone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { phoneNumber: string; code: string }) =>
      profileApi.confirmPhone(input.phoneNumber, input.code),
    onSuccess: (status) => {
      queryClient.setQueryData(profileKeys.phone(), status);
      void queryClient.invalidateQueries({ queryKey: profileKeys.me() });
      void queryClient.invalidateQueries({ queryKey: profileKeys.simulatedInbox() });
    },
  });
}

export function useRemovePhone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => profileApi.removePhone(password),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: profileKeys.phone() });
      void queryClient.invalidateQueries({ queryKey: profileKeys.me() });
    },
  });
}
