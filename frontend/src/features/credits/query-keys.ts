export const creditKeys = {
  all: ["credits"] as const,
  balance: () => [...creditKeys.all, "balance"] as const,
  transactions: (page: number) => [...creditKeys.all, "transactions", page] as const,
};
