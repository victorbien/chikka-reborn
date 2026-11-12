/** Test-only WebSocket. Installed globally in setup.ts, so no test opens a real socket.
 *  Tests drive the "server" side: open(), ready(), push(event), close(code). */
export class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  static latest(): FakeWebSocket | undefined {
    return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  }

  static reset(): void {
    FakeWebSocket.instances = [];
  }

  readonly url: string;
  readyState = FakeWebSocket.CONNECTING;
  sent: Record<string, unknown>[] = [];
  closedWith: number | null = null;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(JSON.parse(data) as Record<string, unknown>);
  }

  close(code = 1000): void {
    if (this.readyState === FakeWebSocket.CLOSED) return;
    this.readyState = FakeWebSocket.CLOSED;
    this.closedWith = code;
  }

  // -- server side -------------------------------------------------------------------------

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  /** Open, then answer the auth frame with `ready`. */
  ready(): void {
    this.open();
    this.push({ type: "ready", connection_id: "c-1", heartbeat_s: 25, server_time: "" });
  }

  push(frame: Record<string, unknown>): void {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(frame) }));
  }

  serverClose(code: number): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code } as CloseEvent);
  }

  framesOfType(type: string): Record<string, unknown>[] {
    return this.sent.filter((frame) => frame.type === type);
  }
}
