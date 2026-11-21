import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type { Balance, TransactionPage } from "@/features/credits/types";

const BASE = "/api/v1/credits";
export const TRANSACTION_PAGE_SIZE = 20;

export function createCreditsApi(client: ApiClient = apiClient) {
  return {
    balance: (signal?: AbortSignal) => client.get<Envelope<Balance>>(BASE, { signal }).then(unwrap),
    transactions: (page: number, signal?: AbortSignal) =>
      client.get<TransactionPage>(`${BASE}/transactions`, {
        signal,
        query: { page, page_size: TRANSACTION_PAGE_SIZE },
      }),
  };
}

export const creditsApi = createCreditsApi();
