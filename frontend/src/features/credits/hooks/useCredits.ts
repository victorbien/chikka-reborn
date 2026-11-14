import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { creditsApi } from "@/features/credits/api";
import { creditKeys } from "@/features/credits/query-keys";
import type { ServerEvent } from "@/lib/realtime/client";
import { useRealtimeEvents } from "@/lib/realtime/provider";

export function useCreditBalance(enabled = true) {
  return useQuery({
    queryKey: creditKeys.balance(),
    queryFn: ({ signal }) => creditsApi.balance(signal),
    staleTime: 30_000,
    enabled,
  });
}

export function useCreditTransactions(page: number) {
  return useQuery({
    queryKey: creditKeys.transactions(page),
    queryFn: ({ signal }) => creditsApi.transactions(page, signal),
    placeholderData: keepPreviousData,
  });
}

/** Refreshes balances when anything that can change them happens: an SMS is queued or its
 *  status moves (hold, spend, release, refund), or a low-credit notice arrives. */
export function useCreditsRealtime(): void {
  const queryClient = useQueryClient();
  useRealtimeEvents((event: ServerEvent) => {
    if (
      event.type === "ready" ||
      event.type === "sms.message.created" ||
      event.type === "sms.message.updated" ||
      event.type === "notification.created"
    ) {
      void queryClient.invalidateQueries({ queryKey: creditKeys.all });
    }
  });
}
