import { WifiOff } from "lucide-react";
import { useRealtimeStatus } from "@/lib/realtime/provider";

/** Connection state in words and an icon, never colour alone (FR-MSG-007 AC4). Messages can
 *  still be sent while reconnecting: sending uses REST, and the list catches up afterwards. */
export function ConnectionBanner() {
  const status = useRealtimeStatus();
  const message =
    status === "offline"
      ? "You are offline. Messages will be sent when you reconnect."
      : status === "reconnecting"
        ? "Reconnecting… New messages may be delayed."
        : null;
  return (
    <div aria-live="polite" className="empty:hidden">
      {message ? (
        <p
          role="status"
          className="flex items-center gap-2 border-b border-border bg-surface-raised px-3 py-2 text-xs"
        >
          <WifiOff aria-hidden className="size-4 text-away" />
          {message}
        </p>
      ) : null}
    </div>
  );
}
