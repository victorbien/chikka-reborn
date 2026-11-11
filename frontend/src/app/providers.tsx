import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { DisplayModeProvider } from "@/lib/display-mode";
import { createQueryClient } from "@/lib/query-client";

export interface AppProvidersProps {
  children: ReactNode;
  /** Tests inject their own client; the app creates one per mount. */
  queryClient?: QueryClient;
}

/** Theme (Classic/Modern display mode) and server-state providers. */
export function AppProviders({ children, queryClient }: AppProvidersProps) {
  const [defaultClient] = useState(createQueryClient);
  return (
    <DisplayModeProvider>
      <QueryClientProvider client={queryClient ?? defaultClient}>{children}</QueryClientProvider>
    </DisplayModeProvider>
  );
}
