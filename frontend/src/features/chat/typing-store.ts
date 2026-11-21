import { useSyncExternalStore } from "react";

/** Ephemeral "is typing" state (FR-MSG-003). Never persisted, never server data. */
const CLEAR_AFTER_MS = 3000;

type Listener = () => void;
const typing = new Map<string, { userId: string; timer: ReturnType<typeof setTimeout> }>();
const listeners = new Set<Listener>();
let version = 0;

function notify() {
  version += 1;
  for (const listener of listeners) listener();
}

export const typingStore = {
  set(conversationId: string, userId: string) {
    const current = typing.get(conversationId);
    if (current) clearTimeout(current.timer);
    typing.set(conversationId, {
      userId,
      timer: setTimeout(() => typingStore.clear(conversationId), CLEAR_AFTER_MS),
    });
    notify();
  },
  clear(conversationId: string) {
    const current = typing.get(conversationId);
    if (!current) return;
    clearTimeout(current.timer);
    typing.delete(conversationId);
    notify();
  },
  reset() {
    for (const { timer } of typing.values()) clearTimeout(timer);
    typing.clear();
    notify();
  },
  get(conversationId: string): string | null {
    return typing.get(conversationId)?.userId ?? null;
  },
};

export function useTypingUser(conversationId: string): string | null {
  useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => version,
  );
  return typingStore.get(conversationId);
}
