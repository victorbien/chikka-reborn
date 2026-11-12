import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup, configure } from "@testing-library/react";
import { sessionStore } from "@/lib/auth/session";
import { FakeWebSocket } from "@/test/fake-websocket";

// No test opens a real socket. Tests that care drive FakeWebSocket.latest().
beforeEach(() => {
  FakeWebSocket.reset();
  if (typeof window !== "undefined") vi.stubGlobal("WebSocket", FakeWebSocket);
});

// Multi-step flows (sign in -> guard -> profile fetch) can exceed the 1 s default when test
// files run in parallel on a busy machine. Waiting longer only changes failure latency.
configure({ asyncUtilTimeout: 5000 });

afterEach(() => {
  cleanup();
  // The live API test runs in the Node environment, which has no DOM storage.
  if (typeof window !== "undefined") window.localStorage.clear();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  sessionStore.reset();
});
