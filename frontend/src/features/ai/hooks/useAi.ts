import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { aiApi } from "@/features/ai/api";
import { aiKeys } from "@/features/ai/query-keys";
import type { AiDecision, AiRequest } from "@/features/ai/types";

export function useAiStatus(enabled = true) {
  return useQuery({
    queryKey: aiKeys.status(),
    queryFn: ({ signal }) => aiApi.status(signal),
    staleTime: 60_000,
    enabled,
    // The assistant is optional: a failed check must not retry in a loop.
    retry: false,
  });
}

export function useSetAiEnabled() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => aiApi.setEnabled(enabled),
    onSuccess: (status) => queryClient.setQueryData(aiKeys.status(), status),
  });
}

/** One request at a time. The result is a draft; nothing here can send a message. */
export function useAiRun() {
  return useMutation({ mutationFn: (request: AiRequest) => aiApi.run(request) });
}

/** Tells the server what the user did with a draft. A failure here never blocks the user. */
export function useRecordDecision() {
  return useMutation({
    mutationFn: ({ assistanceId, decision }: { assistanceId: string; decision: AiDecision }) =>
      aiApi.recordDecision(assistanceId, decision),
  });
}
