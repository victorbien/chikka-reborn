/**
 * Real-time connection to the backend gateway (/ws/v1, docs/api/realtime-api.md).
 *
 * - Authenticates with the first frame (never a URL token).
 * - Reconnects with exponential backoff and full jitter (1 s base, 30 s cap); browser
 *   `online` and tab visibility trigger an early attempt.
 * - 4401 (token expired, signed out): refreshes the access token once, then reconnects.
 *   4403 (account unavailable): stops. Everything else: retries.
 * - The socket is a speed-up only. After every (re)connect listeners get a `ready` event and
 *   resync from REST, which is the source of truth. Duplicate events are ignored by event_id.
 */

export type RealtimeStatus =
  "idle" | "connecting" | "open" | "reconnecting" | "offline" | "stopped";

export interface ServerEvent {
  type: string;
  event_id?: string;
  conversation_id?: string;
  data?: unknown;
  sent_at?: string;
  [key: string]: unknown;
}

export interface RealtimeOptions {
  url: string;
  getToken: () => string | null;
  /** Fresh access token after a 4401, or null when the session is over. */
  refreshToken: () => Promise<string | null>;
  WebSocketImpl?: typeof WebSocket;
  random?: () => number;
}

type EventListener = (event: ServerEvent) => void;
type StatusListener = (status: RealtimeStatus) => void;

export const BACKOFF_BASE_MS = 1000;
export const BACKOFF_CAP_MS = 30_000;
const STABLE_AFTER_MS = 60_000;
const SEEN_LIMIT = 500;

export function backoffDelay(attempt: number, random: () => number = Math.random): number {
  const ceiling = Math.min(BACKOFF_CAP_MS, BACKOFF_BASE_MS * 2 ** attempt);
  return Math.floor(random() * ceiling);
}

/** ws(s)://host/ws/v1 from the API base URL. */
export function realtimeUrl(apiBaseUrl: string): string {
  const url = new URL(apiBaseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/v1";
  url.search = "";
  return url.toString();
}

export class RealtimeClient {
  private status: RealtimeStatus = "idle";
  private socket: WebSocket | null = null;
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private stableTimer: ReturnType<typeof setTimeout> | null = null;
  private running = false;
  private refreshedForThisFailure = false;
  private readonly seen: string[] = [];
  private readonly seenSet = new Set<string>();
  private readonly eventListeners = new Set<EventListener>();
  private readonly statusListeners = new Set<StatusListener>();
  private readonly options: Required<RealtimeOptions>;

  constructor(options: RealtimeOptions) {
    this.options = {
      WebSocketImpl: options.WebSocketImpl ?? WebSocket,
      random: options.random ?? Math.random,
      ...options,
    } as Required<RealtimeOptions>;
  }

  getStatus = (): RealtimeStatus => this.status;

  onStatus = (listener: StatusListener): (() => void) => {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  };

  subscribe = (listener: EventListener): (() => void) => {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  };

  start(): void {
    if (this.running) return;
    this.running = true;
    if (typeof window !== "undefined") {
      window.addEventListener("online", this.handleOnline);
      window.addEventListener("offline", this.handleOffline);
      document.addEventListener("visibilitychange", this.handleVisible);
    }
    this.connect();
  }

  stop(): void {
    this.running = false;
    this.clearTimers();
    if (typeof window !== "undefined") {
      window.removeEventListener("online", this.handleOnline);
      window.removeEventListener("offline", this.handleOffline);
      document.removeEventListener("visibilitychange", this.handleVisible);
    }
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null;
      socket.close(1000, "Client stopped");
    }
    this.setStatus("stopped");
  }

  /** Send an uplink frame. Returns false when not connected (callers fall back to REST). */
  send(frame: Record<string, unknown>): boolean {
    if (this.status !== "open" || !this.socket) return false;
    this.socket.send(JSON.stringify(frame));
    return true;
  }

  private setStatus(next: RealtimeStatus): void {
    if (next === this.status) return;
    this.status = next;
    for (const listener of this.statusListeners) listener(next);
  }

  private clearTimers(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    if (this.stableTimer) clearTimeout(this.stableTimer);
    this.reconnectTimer = this.heartbeatTimer = this.stableTimer = null;
  }

  private connect(): void {
    if (!this.running) return;
    const token = this.options.getToken();
    if (!token) {
      // Signed in but no token in memory yet (page restore): get one first.
      void this.options.refreshToken().then((fresh) => {
        if (fresh) this.connect();
        else this.stop();
      });
      return;
    }
    this.setStatus(this.attempt === 0 ? "connecting" : "reconnecting");
    const socket = new this.options.WebSocketImpl(this.options.url);
    this.socket = socket;
    socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token }));
    socket.onmessage = (message: MessageEvent) => this.handleFrame(message.data);
    socket.onclose = (event: CloseEvent) => this.handleClose(socket, event.code);
    socket.onerror = () => {
      /* onclose follows and decides what to do */
    };
  }

  private handleFrame(raw: unknown): void {
    if (typeof raw !== "string") return;
    let frame: ServerEvent;
    try {
      frame = JSON.parse(raw) as ServerEvent;
    } catch {
      return;
    }
    if (typeof frame.type !== "string") return;
    if (frame.type === "pong" || frame.type === "auth.ok") return;
    if (frame.type === "ready") {
      this.refreshedForThisFailure = false;
      this.setStatus("open");
      const seconds = typeof frame.heartbeat_s === "number" ? frame.heartbeat_s : 25;
      this.heartbeatTimer = setInterval(() => this.send({ type: "ping" }), seconds * 1000);
      // Reset the backoff only once the connection has proved stable.
      this.stableTimer = setTimeout(() => {
        this.attempt = 0;
      }, STABLE_AFTER_MS);
      this.emit(frame);
      return;
    }
    if (frame.event_id) {
      if (this.seenSet.has(frame.event_id)) return;
      this.seenSet.add(frame.event_id);
      this.seen.push(frame.event_id);
      if (this.seen.length > SEEN_LIMIT) this.seenSet.delete(this.seen.shift() as string);
    }
    this.emit(frame);
  }

  private emit(frame: ServerEvent): void {
    for (const listener of this.eventListeners) {
      try {
        listener(frame);
      } catch {
        /* one faulty listener must not break the others */
      }
    }
  }

  private handleClose(socket: WebSocket, code: number): void {
    if (socket !== this.socket) return;
    this.socket = null;
    this.clearTimers();
    if (!this.running) return;
    if (code === 4403) {
      this.stop();
      return;
    }
    if (code === 4401 && !this.refreshedForThisFailure) {
      this.refreshedForThisFailure = true;
      this.setStatus("reconnecting");
      void this.options.refreshToken().then((fresh) => {
        if (!this.running) return;
        if (fresh) this.connect();
        else this.stop();
      });
      return;
    }
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (!this.running) return;
    const offline = typeof navigator !== "undefined" && navigator.onLine === false;
    this.setStatus(offline ? "offline" : "reconnecting");
    const delay = backoffDelay(this.attempt, this.options.random);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private reconnectNow(): void {
    if (!this.running || this.socket) return;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.connect();
  }

  private handleOnline = (): void => this.reconnectNow();

  private handleOffline = (): void => {
    if (this.running && this.status !== "open") this.setStatus("offline");
  };

  private handleVisible = (): void => {
    if (document.visibilityState === "visible") this.reconnectNow();
  };
}
