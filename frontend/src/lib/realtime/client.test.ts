import { afterEach, describe, expect, it, vi } from "vitest";
import { backoffDelay, BACKOFF_CAP_MS, RealtimeClient, realtimeUrl } from "@/lib/realtime/client";
import { FakeWebSocket } from "@/test/fake-websocket";

function makeClient(overrides: { refresh?: () => Promise<string | null> } = {}) {
  const refreshToken = vi.fn(overrides.refresh ?? (async () => "fresh-token"));
  const client = new RealtimeClient({
    url: "ws://api.test/ws/v1",
    getToken: () => "token-1",
    refreshToken,
    WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    random: () => 0.5,
  });
  return { client, refreshToken };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("realtime client", () => {
  it("builds the socket URL from the API base URL", () => {
    expect(realtimeUrl("http://localhost:8000")).toBe("ws://localhost:8000/ws/v1");
    expect(realtimeUrl("https://api.example.com/")).toBe("wss://api.example.com/ws/v1");
  });

  it("backs off exponentially with full jitter, capped at 30 seconds", () => {
    expect(backoffDelay(0, () => 0.999)).toBeLessThan(1000);
    expect(backoffDelay(3, () => 0.999)).toBeLessThan(8000);
    expect(backoffDelay(20, () => 0.999)).toBeLessThan(BACKOFF_CAP_MS);
    expect(backoffDelay(5, () => 0)).toBe(0);
  });

  it("authenticates with the first frame, not the URL", () => {
    const { client } = makeClient();
    client.start();
    const socket = FakeWebSocket.latest();
    expect(socket?.url).toBe("ws://api.test/ws/v1");
    expect(socket?.url).not.toContain("token");
    socket?.open();
    expect(socket?.sent[0]).toEqual({ type: "auth", token: "token-1" });
    client.stop();
  });

  it("reports status, heartbeats, and ignores duplicate events", () => {
    vi.useFakeTimers();
    const { client } = makeClient();
    const statuses: string[] = [];
    const events: string[] = [];
    client.onStatus((status) => statuses.push(status));
    client.subscribe((event) => events.push(event.type));
    client.start();
    const socket = FakeWebSocket.latest() as FakeWebSocket;
    socket.ready();
    expect(client.getStatus()).toBe("open");
    vi.advanceTimersByTime(25_000);
    expect(socket.framesOfType("ping")).toHaveLength(1);
    socket.push({ type: "message.created", event_id: "e-1" });
    socket.push({ type: "message.created", event_id: "e-1" });
    expect(events).toEqual(["ready", "message.created"]);
    expect(statuses).toEqual(["connecting", "open"]);
    client.stop();
  });

  it("reconnects after a drop, and resyncs via ready", () => {
    vi.useFakeTimers();
    const { client } = makeClient();
    const events: string[] = [];
    client.subscribe((event) => events.push(event.type));
    client.start();
    (FakeWebSocket.latest() as FakeWebSocket).ready();
    (FakeWebSocket.latest() as FakeWebSocket).serverClose(1006);
    expect(client.getStatus()).toBe("reconnecting");
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);
    (FakeWebSocket.latest() as FakeWebSocket).ready();
    expect(events.filter((e) => e === "ready")).toHaveLength(2);
    client.stop();
  });

  it("refreshes the token once on 4401, then reconnects with the new token", async () => {
    const { client, refreshToken } = makeClient();
    client.start();
    (FakeWebSocket.latest() as FakeWebSocket).serverClose(4401);
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2));
    expect(refreshToken).toHaveBeenCalledTimes(1);
    client.stop();
  });

  it("stops when the session cannot be refreshed or the account is unavailable", async () => {
    const expired = makeClient({ refresh: async () => null });
    expired.client.start();
    (FakeWebSocket.latest() as FakeWebSocket).serverClose(4401);
    await vi.waitFor(() => expect(expired.client.getStatus()).toBe("stopped"));

    const forbidden = makeClient();
    forbidden.client.start();
    (FakeWebSocket.latest() as FakeWebSocket).serverClose(4403);
    expect(forbidden.client.getStatus()).toBe("stopped");
    expect(forbidden.refreshToken).not.toHaveBeenCalled();
  });

  it("only sends uplink frames while connected", () => {
    const { client } = makeClient();
    expect(client.send({ type: "typing" })).toBe(false);
    client.start();
    const socket = FakeWebSocket.latest() as FakeWebSocket;
    socket.ready();
    expect(client.send({ type: "typing", conversation_id: "k-1" })).toBe(true);
    expect(socket.framesOfType("typing")).toHaveLength(1);
    client.stop();
    expect(socket.closedWith).toBe(1000);
  });
});
