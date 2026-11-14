/** Browser (system) notifications. Only shown with the user's permission, only for notifications
 *  the server flagged for the browser (preferences and quiet hours already applied), and only
 *  while the app is in the background: an open, visible app shows the in-app badge instead. */

export type BrowserPermission = NotificationPermission | "unsupported";

export function browserPermission(): BrowserPermission {
  return typeof Notification === "undefined" ? "unsupported" : Notification.permission;
}

/** Must be called from a click: browsers ignore or block prompts that are not user-initiated. */
export async function requestBrowserPermission(): Promise<BrowserPermission> {
  if (typeof Notification === "undefined") return "unsupported";
  return Notification.requestPermission();
}

export interface BrowserNotificationOptions {
  title: string;
  body?: string | null;
  /** Notifications with the same tag replace each other instead of piling up. */
  tag: string;
  onOpen: () => void;
}

export function canShowBrowserNotification(): boolean {
  return browserPermission() === "granted" && document.visibilityState === "hidden";
}

export function showBrowserNotification({
  title,
  body,
  tag,
  onOpen,
}: BrowserNotificationOptions): boolean {
  if (!canShowBrowserNotification()) return false;
  try {
    const shown = new Notification(title, { body: body ?? undefined, tag });
    shown.onclick = () => {
      window.focus();
      onOpen();
      shown.close();
    };
    return true;
  } catch {
    // Some browsers refuse the constructor (for example on mobile). The badge still works.
    return false;
  }
}
