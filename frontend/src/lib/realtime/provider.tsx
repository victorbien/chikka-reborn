import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { sessionStore, useSession } from "@/lib/auth/session";
import { env } from "@/lib/env";
import {
  RealtimeClient,
  realtimeUrl,
  type RealtimeStatus,
  type ServerEvent,
} from "@/lib/realtime/client";

const RealtimeContext = createContext<RealtimeClient | null>(null);

/** One connection per tab while signed in. Signing out closes it. */
export function RealtimeProvider({ children, enabled }: { children: ReactNode; enabled: boolean }) {
  const session = useSession();
  const [client] = useState(
    () =>
      new RealtimeClient({
        url: realtimeUrl(env.VITE_API_BASE_URL),
        getToken: () => sessionStore.getSnapshot().accessToken,
        refreshToken: () => sessionStore.refresh(),
      }),
  );
  const active = enabled && session.status === "signed-in";

  useEffect(() => {
    if (!active) return undefined;
    client.start();
    return () => client.stop();
  }, [active, client]);

  return <RealtimeContext.Provider value={client}>{children}</RealtimeContext.Provider>;
}

function useClient(): RealtimeClient | null {
  return useContext(RealtimeContext);
}

export function useRealtimeStatus(): RealtimeStatus {
  const client = useClient();
  return useSyncExternalStore(
    (listener) => (client ? client.onStatus(listener) : () => undefined),
    () => (client ? client.getStatus() : "idle"),
  );
}

/** Subscribe to server events. The latest handler is always used (no resubscribe churn). */
export function useRealtimeEvents(handler: (event: ServerEvent) => void): void {
  const client = useClient();
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  });
  useEffect(() => {
    if (!client) return undefined;
    return client.subscribe((event) => latest.current(event));
  }, [client]);
}

/** Send an uplink frame (ack, typing). Returns false when the socket is not open. */
export function useRealtimeSend(): (frame: Record<string, unknown>) => boolean {
  const client = useClient();
  return (frame) => (client ? client.send(frame) : false);
}
