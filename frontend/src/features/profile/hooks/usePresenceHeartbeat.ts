import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { profileApi } from "@/features/profile/api";
import { profileKeys } from "@/features/profile/query-keys";

export const HEARTBEAT_MS = 30_000;
export const IDLE_AFTER_MS = 5 * 60_000;

const ACTIVITY_EVENTS = ["pointerdown", "keydown", "scroll", "touchstart"] as const;

let lastActivity = Date.now();
let listeners = 0;
const markActive = () => {
  lastActivity = Date.now();
};

function useActivityTracking(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    if (listeners++ === 0) {
      lastActivity = Date.now();
      for (const name of ACTIVITY_EVENTS)
        window.addEventListener(name, markActive, { passive: true });
    }
    return () => {
      if (--listeners === 0) {
        for (const name of ACTIVITY_EVENTS) window.removeEventListener(name, markActive);
      }
    };
  }, [enabled]);
}

/**
 * Presence heartbeat as a polling query (FR-AUTH-013): every 30 seconds, idle after 5 minutes
 * without input. When heartbeats stop (tab closed, signed out) the server shows the user
 * offline after 60 seconds. Every component that reads presence shares this one query.
 */
export function usePresence(enabled: boolean) {
  useActivityTracking(enabled);
  return useQuery({
    queryKey: profileKeys.presence(),
    queryFn: () => profileApi.heartbeat(Date.now() - lastActivity >= IDLE_AFTER_MS),
    enabled,
    refetchInterval: enabled ? HEARTBEAT_MS : false,
    refetchIntervalInBackground: true,
    staleTime: HEARTBEAT_MS,
    // Best effort: a failed heartbeat must never show an error or retry aggressively.
    retry: false,
  });
}
