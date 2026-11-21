import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  HEARTBEAT_MS,
  IDLE_AFTER_MS,
  usePresence,
} from "@/features/profile/hooks/usePresenceHeartbeat";
import { useModePreference } from "@/features/profile/hooks/useModePreference";
import { useArrowKeyNavigation } from "@/hooks/useArrowKeyNavigation";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useSlashToSearch } from "@/hooks/useSlashToSearch";
import { DisplayModeProvider } from "@/lib/display-mode";
import { fail, makeProfile, mockApi, ok } from "@/test/api-mock";

function queryWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <DisplayModeProvider>{children}</DisplayModeProvider>
      </QueryClientProvider>
    );
  };
}

describe("useDebouncedValue", () => {
  beforeEach(() => vi.useFakeTimers());

  it("keeps the old value until the input has been still for the delay", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: "a" },
    });
    expect(result.current).toBe("a");

    rerender({ value: "ab" });
    act(() => vi.advanceTimersByTime(299));
    expect(result.current).toBe("a");
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe("ab");
  });

  it("restarts the wait on every change, so only the last value is published", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: "a" },
    });
    rerender({ value: "ab" });
    act(() => vi.advanceTimersByTime(200));
    rerender({ value: "abc" });
    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe("a");
    act(() => vi.advanceTimersByTime(100));
    expect(result.current).toBe("abc");
  });
});

describe("useMediaQuery", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reports false where matchMedia does not exist", () => {
    vi.stubGlobal("matchMedia", undefined);
    const { result } = renderHook(() => useMediaQuery("(min-width: 1024px)"));
    expect(result.current).toBe(false);
  });

  it("follows the query as the window changes size and stops listening on unmount", () => {
    let matches = false;
    const listeners = new Set<() => void>();
    vi.stubGlobal("matchMedia", () => ({
      get matches() {
        return matches;
      },
      addEventListener: (_: string, fn: () => void) => listeners.add(fn),
      removeEventListener: (_: string, fn: () => void) => listeners.delete(fn),
    }));

    const { result, unmount } = renderHook(() => useMediaQuery("(min-width: 1024px)"));
    expect(result.current).toBe(false);

    matches = true;
    act(() => listeners.forEach((notify) => notify()));
    expect(result.current).toBe(true);

    unmount();
    expect(listeners.size).toBe(0);
  });
});

describe("useArrowKeyNavigation", () => {
  function List({ disabledSecond = false }: { disabledSecond?: boolean }) {
    const onKeyDown = useArrowKeyNavigation("button");
    return (
      <div role="group" aria-label="list" onKeyDown={onKeyDown}>
        <button>one</button>
        <button disabled={disabledSecond}>two</button>
        <button>three</button>
      </div>
    );
  }

  it("moves focus with the arrow keys and stops at both ends", async () => {
    const user = userEvent.setup();
    render(<List />);
    screen.getByRole("button", { name: "one" }).focus();

    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("button", { name: "two" })).toHaveFocus();
    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(screen.getByRole("button", { name: "three" })).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(screen.getByRole("button", { name: "two" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("button", { name: "one" })).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(screen.getByRole("button", { name: "one" })).toHaveFocus();
    await user.keyboard("{End}");
    expect(screen.getByRole("button", { name: "three" })).toHaveFocus();
  });

  it("skips disabled items and ignores keys with a modifier", async () => {
    const user = userEvent.setup();
    render(<List disabledSecond />);
    screen.getByRole("button", { name: "one" }).focus();

    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("button", { name: "three" })).toHaveFocus();

    screen.getByRole("button", { name: "one" }).focus();
    await user.keyboard("{Control>}{ArrowDown}{/Control}");
    expect(screen.getByRole("button", { name: "one" })).toHaveFocus();
  });
});

describe("useSlashToSearch", () => {
  function Page() {
    const ref = useRef<HTMLDivElement>(null);
    useSlashToSearch(ref);
    return (
      <div ref={ref}>
        <input type="search" aria-label="Search" />
        <input type="text" aria-label="Name" />
      </div>
    );
  }

  it("focuses the search box when / is pressed outside a text field", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.keyboard("/");
    expect(screen.getByRole("searchbox", { name: "Search" })).toHaveFocus();
  });

  it("leaves / alone while the person is typing in another field", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.click(screen.getByRole("textbox", { name: "Name" }));
    await user.keyboard("a/b");
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("a/b");
    expect(screen.getByRole("searchbox", { name: "Search" })).not.toHaveFocus();
  });
});

describe("usePresence", () => {
  beforeEach(() => {
    vi.useFakeTimers({
      toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"],
    });
  });

  it("sends a heartbeat every 30 seconds and reports idle only after 5 quiet minutes", async () => {
    const api = mockApi({
      "POST /api/v1/users/me/presence/heartbeat": ok({
        status: "online",
        preference: "online",
        last_seen_at: "2026-11-11T00:00:00Z",
      }),
    });
    renderHook(() => usePresence(true), { wrapper: queryWrapper() });
    await act(() => vi.advanceTimersByTimeAsync(0));
    const beats = () => api.callsTo("POST", "/api/v1/users/me/presence/heartbeat");
    expect(beats()).toHaveLength(1);
    expect(beats()[0]?.body).toEqual({ idle: false });

    await act(() => vi.advanceTimersByTimeAsync(HEARTBEAT_MS));
    expect(beats()).toHaveLength(2);

    await act(() => vi.advanceTimersByTimeAsync(IDLE_AFTER_MS));
    expect(beats().at(-1)?.body).toEqual({ idle: true });

    // Any input counts as activity again.
    act(() => {
      window.dispatchEvent(new Event("keydown"));
    });
    await act(() => vi.advanceTimersByTimeAsync(HEARTBEAT_MS));
    expect(beats().at(-1)?.body).toEqual({ idle: false });
  });

  it("does nothing while signed out", async () => {
    const api = mockApi({});
    renderHook(() => usePresence(false), { wrapper: queryWrapper() });
    await act(() => vi.advanceTimersByTimeAsync(HEARTBEAT_MS * 3));
    expect(api.calls).toHaveLength(0);
  });
});

describe("useModePreference", () => {
  beforeEach(() => window.localStorage.clear());

  it("applies the new mode at once and saves it to the profile", async () => {
    const api = mockApi({
      "PATCH /api/v1/users/me": ok(makeProfile({ ui_mode: "classic" })),
    });
    const { result } = renderHook(() => useModePreference(), { wrapper: queryWrapper() });
    expect(result.current.mode).toBe("modern");

    await act(async () => result.current.choose("classic"));
    expect(result.current.mode).toBe("classic");
    expect(document.documentElement.dataset.mode).toBe("classic");
    expect(api.callsTo("PATCH", "/api/v1/users/me")[0]?.body).toEqual({ ui_mode: "classic" });
  });

  it("does not call the server when the mode is unchanged", async () => {
    const api = mockApi({});
    const { result } = renderHook(() => useModePreference(), { wrapper: queryWrapper() });
    await act(async () => result.current.choose("modern"));
    expect(api.calls).toHaveLength(0);
  });

  it("goes back to the previous mode when saving fails", async () => {
    mockApi({ "PATCH /api/v1/users/me": fail(500, "internal_error", "Something went wrong.") });
    const { result } = renderHook(() => useModePreference(), { wrapper: queryWrapper() });

    await act(async () => result.current.choose("classic"));
    await vi.waitFor(() => expect(result.current.mode).toBe("modern"));
    expect(result.current.saveFailed).toBe(true);
  });
});
