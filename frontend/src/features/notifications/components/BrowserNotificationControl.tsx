import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  browserPermission,
  requestBrowserPermission,
  type BrowserPermission,
} from "@/lib/browser-notifications";

const TEXT: Record<BrowserPermission, string> = {
  default: "Get a system notification when something arrives while this tab is in the background.",
  granted: "Browser notifications are on. They appear only while this tab is in the background.",
  denied:
    "Browser notifications are blocked. Allow them for this site in your browser settings to turn them on.",
  unsupported: "This browser does not support system notifications. The in-app badge still works.",
};

/** Asks for browser notification permission, only when the user presses the button. */
export function BrowserNotificationControl({ compact = false }: { compact?: boolean }) {
  const [permission, setPermission] = useState<BrowserPermission>(browserPermission);
  if (compact && permission !== "default") return null;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-panel border border-border p-3 text-sm">
      <p className="flex-1">{TEXT[permission]}</p>
      {permission === "default" ? (
        <Button size="sm" onClick={() => void requestBrowserPermission().then(setPermission)}>
          Turn on browser notifications
        </Button>
      ) : null}
    </div>
  );
}
