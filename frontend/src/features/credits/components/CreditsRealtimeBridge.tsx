import { useCreditsRealtime } from "@/features/credits/hooks/useCredits";

/** Renders nothing. Keeps balances fresh when messages change state, on every page. */
export function CreditsRealtimeBridge() {
  useCreditsRealtime();
  return null;
}
