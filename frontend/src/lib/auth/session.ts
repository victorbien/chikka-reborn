import { useSyncExternalStore } from "react";
import type { ApiClient } from "@/lib/api/client";
import type { Envelope } from "@/lib/api/envelope";

/**
 * Client session state (ADL-011). The access token lives only in memory; the refresh token
 * is an httpOnly cookie the browser sends to /api/v1/auth. Nothing goes to localStorage.
 *
 *   unknown    - restoring from the refresh cookie on page load
 *   signed-in  - an access token is held
 *   signed-out - no session (never had one, signed out, or refresh failed)
 */
export type SessionStatus = "unknown" | "signed-in" | "signed-out";

export interface SessionSnapshot {
  status: SessionStatus;
  accessToken: string | null;
}

export interface TokenData {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export const CSRF_HEADERS = { "X-Chikka-CSRF": "1" } as const;

type Listener = () => void;

export class SessionStore {
  private snapshot: SessionSnapshot = { status: "unknown", accessToken: null };
  private readonly listeners = new Set<Listener>();
  private refreshing: Promise<string | null> | null = null;
  private client: ApiClient | null = null;

  getSnapshot = (): SessionSnapshot => this.snapshot;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  /** Wire the API client so requests carry the token and retry once after a refresh. */
  attach(client: ApiClient): void {
    this.client = client;
    client.setAuthHandlers({
      getToken: () => this.snapshot.accessToken,
      refresh: () => this.refresh(),
    });
  }

  signIn(tokens: TokenData): void {
    this.set({ status: "signed-in", accessToken: tokens.access_token });
  }

  signOut(): void {
    this.set({ status: "signed-out", accessToken: null });
  }

  /** Back to "unknown" (page-load state). Used by tests to isolate the singleton. */
  reset(): void {
    this.refreshing = null;
    this.set({ status: "unknown", accessToken: null });
  }

  /** Single-flight: concurrent 401s share one refresh call. */
  refresh(): Promise<string | null> {
    if (!this.refreshing) {
      this.refreshing = this.doRefresh().finally(() => {
        this.refreshing = null;
      });
    }
    return this.refreshing;
  }

  private async doRefresh(): Promise<string | null> {
    if (!this.client) return null;
    try {
      const body = await this.client.post<Envelope<TokenData>>("/api/v1/auth/refresh", undefined, {
        headers: CSRF_HEADERS,
        skipAuthRefresh: true,
      });
      this.signIn(body.data);
      return body.data.access_token;
    } catch {
      this.signOut();
      return null;
    }
  }

  private set(next: SessionSnapshot): void {
    if (next.status === this.snapshot.status && next.accessToken === this.snapshot.accessToken) {
      return;
    }
    this.snapshot = next;
    for (const listener of this.listeners) listener();
  }
}

export const sessionStore = new SessionStore();

export function useSession(store: SessionStore = sessionStore): SessionSnapshot {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
}
