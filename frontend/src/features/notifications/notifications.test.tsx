import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BrowserNotificationControl } from "@/features/notifications/components/BrowserNotificationControl";
import { NotificationBell } from "@/features/notifications/components/NotificationBell";
import { NotificationCentre } from "@/features/notifications/components/NotificationCentre";
import { NotificationPreferencesForm } from "@/features/notifications/components/NotificationPreferencesForm";
import { handleNotificationEvent } from "@/features/notifications/hooks/useNotificationRealtime";
import { notificationLink } from "@/features/notifications/links";
import { notificationKeys } from "@/features/notifications/query-keys";
import {
  NOTIFICATION_TYPES,
  type AppNotification,
  type NotificationPreferences,
} from "@/features/notifications/types";
import { fail, mockApi, ok, type MockReply } from "@/test/api-mock";

const BASE = "/api/v1/notifications";

function note(overrides: Partial<AppNotification> = {}): AppNotification {
  return {
    id: "n-1",
    type: "new_message",
    title: "New message from Bob Cruz",
    body: null,
    reference_type: "conversation",
    reference_id: "c-1",
    occurrence_count: 1,
    is_read: false,
    created_at: "2026-11-14T08:00:00Z",
    ...overrides,
  };
}

function page(items: AppNotification[], overrides = {}): MockReply {
  return {
    status: 200,
    body: {
      data: items,
      pagination: {
        total: items.length,
        page: 1,
        page_size: 20,
        has_next: false,
        has_prev: false,
        ...overrides,
      },
      request_id: "req-test",
    },
  };
}

function preferences(overrides: Partial<NotificationPreferences> = {}): NotificationPreferences {
  return {
    types: NOTIFICATION_TYPES.map((type) => ({
      type,
      in_app: true,
      push: type !== "sms_delivered" && type !== "contact_accepted",
      email: type === "system" || type === "security",
      in_app_locked: ["sms_failed", "system", "security"].includes(type),
    })),
    quiet_hours_start: null,
    quiet_hours_end: null,
    show_previews: false,
    low_balance_threshold_units: 500,
    low_balance_threshold_credits: 5,
    email_disabled: false,
    email_simulated: true,
    ...overrides,
  };
}

function newClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function wrap(ui: ReactNode, client = newClient()) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
});

describe("notification centre", () => {
  it("lists notifications newest first with unread state, grouping and no invented text", async () => {
    mockApi({
      [`GET ${BASE}`]: page([
        note({ occurrence_count: 3 }),
        note({
          id: "n-2",
          type: "sms_delivered",
          title: "Simulated SMS delivered",
          reference_type: "message",
          reference_id: "m-1",
          is_read: true,
        }),
      ]),
      [`GET ${BASE}/unread-count`]: ok({ unread_count: 1 }),
    });
    wrap(<NotificationCentre />);

    const list = await screen.findByRole("list", { name: "Notifications" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]!).getByText("New message from Bob Cruz")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("(3)")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("New")).toBeInTheDocument();
    expect(within(rows[0]!).getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "/messages/c-1",
    );
    expect(within(rows[1]!).queryByText("New")).not.toBeInTheDocument();
    expect(
      within(rows[1]!).queryByRole("button", { name: "Mark as read" }),
    ).not.toBeInTheDocument();
    expect(await screen.findByText("1 unread")).toBeInTheDocument();
  });

  it("marks one notification as read", async () => {
    const api = mockApi({
      [`GET ${BASE}`]: page([note()]),
      [`GET ${BASE}/unread-count`]: ok({ unread_count: 1 }),
      [`POST ${BASE}/n-1/read`]: ok(note({ is_read: true })),
    });
    const user = userEvent.setup();
    wrap(<NotificationCentre />);

    await user.click(await screen.findByRole("button", { name: "Mark as read" }));

    await waitFor(() => expect(api.callsTo("POST", `${BASE}/n-1/read`)).toHaveLength(1));
  });

  it("marks everything as read and disables the button when nothing is unread", async () => {
    let unread = 2;
    const api = mockApi({
      [`GET ${BASE}`]: page([note(), note({ id: "n-2" })]),
      [`GET ${BASE}/unread-count`]: () => ok({ unread_count: unread }),
      [`POST ${BASE}/read-all`]: () => {
        unread = 0;
        return ok({ updated: 2, unread_count: 0 });
      },
    });
    const user = userEvent.setup();
    wrap(<NotificationCentre />);

    await user.click(await screen.findByRole("button", { name: "Mark all as read" }));

    await waitFor(() => expect(api.callsTo("POST", `${BASE}/read-all`)).toHaveLength(1));
    expect(await screen.findByText("You are all caught up.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark all as read" })).toBeDisabled();
  });

  it("filters to unread and dismisses", async () => {
    const api = mockApi({
      [`GET ${BASE}`]: page([note()]),
      [`GET ${BASE}/unread-count`]: ok({ unread_count: 1 }),
      [`POST ${BASE}/n-1/dismiss`]: ok({ unread_count: 0 }),
    });
    const user = userEvent.setup();
    wrap(<NotificationCentre />);

    await user.click(await screen.findByRole("button", { name: "Show unread only" }));
    await waitFor(() =>
      expect(
        api.callsTo("GET", BASE).some((call) => call.search.includes("unread_only=true")),
      ).toBe(true),
    );
    await user.click(await screen.findByRole("button", { name: /Dismiss: New message/ }));

    await waitFor(() => expect(api.callsTo("POST", `${BASE}/n-1/dismiss`)).toHaveLength(1));
  });

  it("has an empty state, a loading state and an error with a retry", async () => {
    let calls = 0;
    mockApi({
      [`GET ${BASE}`]: () => {
        calls += 1;
        return calls === 1 ? fail(503, "service_unavailable", "Try again soon.") : page([]);
      },
      [`GET ${BASE}/unread-count`]: ok({ unread_count: 0 }),
    });
    const user = userEvent.setup();
    wrap(<NotificationCentre />);

    expect(screen.getByText("Loading your notifications…")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Try again" }));

    expect(await screen.findByText("No notifications yet")).toBeInTheDocument();
  });
});

describe("notification bell", () => {
  it("announces the unread count", async () => {
    mockApi({ [`GET ${BASE}/unread-count`]: ok({ unread_count: 3 }) });
    wrap(<NotificationBell />);

    const link = await screen.findByRole("link", { name: "Notifications, 3 unread" });
    expect(link).toHaveAttribute("href", "/notifications");
  });

  it("shows no badge when everything is read", async () => {
    const api = mockApi({ [`GET ${BASE}/unread-count`]: ok({ unread_count: 0 }) });
    wrap(<NotificationBell />);

    await waitFor(() => expect(api.callsTo("GET", `${BASE}/unread-count`)).toHaveLength(1));
    expect(screen.getByRole("link", { name: "Notifications" })).toBeInTheDocument();
  });
});

describe("notification links", () => {
  it.each([
    [{ type: "new_message", reference_type: "conversation", reference_id: "c-9" }, "/messages/c-9"],
    [{ type: "sms_failed", reference_type: "message", reference_id: "m-1" }, "/sms"],
    [
      { type: "contact_request", reference_type: "contact_request", reference_id: "r" },
      "/contacts",
    ],
    [{ type: "low_balance", reference_type: null, reference_id: null }, "/credits"],
    [{ type: "security", reference_type: null, reference_id: null }, "/settings/profile"],
    [{ type: "system", reference_type: "credit_transaction", reference_id: "t" }, "/credits"],
    [{ type: "system", reference_type: null, reference_id: null }, null],
  ] as const)("%j leads to %s", (item, expected) => {
    expect(notificationLink(item)).toBe(expected);
  });
});

describe("notification settings", () => {
  const PUT = `PUT ${BASE}/preferences`;

  it("shows every type and channel, with mandatory in-app notices locked", async () => {
    mockApi({ [`GET ${BASE}/preferences`]: ok(preferences()) });
    wrap(<NotificationPreferencesForm />);

    expect(
      await screen.findByRole("checkbox", { name: "New messages by email" }),
    ).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Security alerts by email" })).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "SMS delivered in the browser" }),
    ).not.toBeChecked();
    // Failed SMS, system and security notices cannot be switched off in the app.
    expect(
      screen.queryByRole("checkbox", { name: "SMS failed in the app" }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText("Always on")).toHaveLength(3);
    expect(screen.getByText(/nothing is sent to a real mailbox/)).toBeInTheDocument();
  });

  it("saves the changed settings", async () => {
    const api = mockApi({
      [`GET ${BASE}/preferences`]: ok(preferences()),
      [PUT]: ok(preferences({ show_previews: true })),
    });
    const user = userEvent.setup();
    wrap(<NotificationPreferencesForm />);

    await user.click(await screen.findByRole("checkbox", { name: "New messages by email" }));
    await user.click(screen.getByRole("checkbox", { name: "Contact requests in the browser" }));
    await user.click(screen.getByRole("checkbox", { name: /Show message previews/ }));
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    expect(await screen.findByText("Your notification settings were saved.")).toBeInTheDocument();
    const body = api.callsTo("PUT", `${BASE}/preferences`)[0]?.body as {
      types: Record<string, Record<string, boolean>>;
      show_previews: boolean;
      quiet_hours_start: string | null;
      low_balance_threshold_units: number;
    };
    expect(body.types.new_message).toEqual({ in_app: true, push: true, email: true });
    expect(body.types.contact_request?.push).toBe(false);
    expect(body.types.sms_failed?.in_app).toBe(true);
    expect(body.show_previews).toBe(true);
    expect(body.quiet_hours_start).toBeNull();
    expect(body.low_balance_threshold_units).toBe(500);
  });

  it("saves quiet hours and the low-credit threshold in credits", async () => {
    const api = mockApi({
      [`GET ${BASE}/preferences`]: ok(preferences()),
      [PUT]: ok(preferences()),
    });
    const user = userEvent.setup();
    wrap(<NotificationPreferencesForm />);

    await user.click(await screen.findByRole("checkbox", { name: "Use quiet hours" }));
    const threshold = screen.getByLabelText(/Warn me when my demo credits fall to/);
    await user.clear(threshold);
    await user.type(threshold, "12.5");
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(() => expect(api.callsTo("PUT", `${BASE}/preferences`)).toHaveLength(1));
    const body = api.callsTo("PUT", `${BASE}/preferences`)[0]?.body as Record<string, unknown>;
    expect(body.quiet_hours_start).toBe("22:00");
    expect(body.quiet_hours_end).toBe("07:00");
    expect(body.low_balance_threshold_units).toBe(1250);
  });

  it("rejects an invalid threshold and identical quiet hours before calling the server", async () => {
    const api = mockApi({ [`GET ${BASE}/preferences`]: ok(preferences()) });
    const user = userEvent.setup();
    wrap(<NotificationPreferencesForm />);

    const threshold = await screen.findByLabelText(/Warn me when my demo credits fall to/);
    await user.clear(threshold);
    await user.type(threshold, "0");
    await user.click(screen.getByRole("checkbox", { name: "Use quiet hours" }));
    const [from, until] = [screen.getByLabelText(/From/), screen.getByLabelText(/Until/)];
    await user.clear(from);
    await user.type(from, "08:00");
    await user.clear(until);
    await user.type(until, "08:00");
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    expect(await screen.findByText("At least 1 credit")).toBeInTheDocument();
    expect(screen.getByText("Start and end must be different")).toBeInTheDocument();
    expect(api.callsTo("PUT", `${BASE}/preferences`)).toHaveLength(0);
  });

  it("shows a server error and a switched-off email notice", async () => {
    mockApi({
      [`GET ${BASE}/preferences`]: ok(preferences({ email_disabled: true })),
      [PUT]: fail(500, "internal_error", "Something went wrong."),
    });
    const user = userEvent.setup();
    wrap(<NotificationPreferencesForm />);

    expect(await screen.findByText(/Email is switched off for your account/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2)); // switched-off notice + save error
    expect(screen.queryByText("Your notification settings were saved.")).not.toBeInTheDocument();
  });
});

describe("browser notifications", () => {
  function stubNotification(permission: NotificationPermission) {
    const shown: {
      title: string;
      options?: NotificationOptions;
      close: () => void;
      onclick: (() => void) | null;
    }[] = [];
    class FakeNotification {
      static permission: NotificationPermission = permission;
      static requestPermission = vi.fn(async () => {
        FakeNotification.permission = "granted";
        return "granted" as NotificationPermission;
      });
      onclick: (() => void) | null = null;
      close = vi.fn();
      constructor(
        public title: string,
        public options?: NotificationOptions,
      ) {
        shown.push(this);
      }
    }
    vi.stubGlobal("Notification", FakeNotification);
    return { shown, FakeNotification };
  }

  function hidden(value: boolean) {
    Object.defineProperty(document, "visibilityState", {
      value: value ? "hidden" : "visible",
      configurable: true,
    });
  }

  const created = (browser: boolean, unread = 4) => ({
    type: "notification.created",
    data: { notification: note({ id: "n-9" }), browser, unread_count: unread },
  });

  it("only asks for permission when the user presses the button", async () => {
    const { FakeNotification } = stubNotification("default");
    const user = userEvent.setup();
    wrap(<BrowserNotificationControl />);

    expect(FakeNotification.requestPermission).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Turn on browser notifications" }));

    expect(FakeNotification.requestPermission).toHaveBeenCalledOnce();
    expect(await screen.findByText(/Browser notifications are on/)).toBeInTheDocument();
  });

  it("explains a blocked or unsupported browser instead of nagging", () => {
    stubNotification("denied");
    const { unmount } = wrap(<BrowserNotificationControl />);
    expect(screen.getByText(/blocked/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    unmount();

    vi.stubGlobal("Notification", undefined);
    wrap(<BrowserNotificationControl />);
    expect(screen.getByText(/does not support system notifications/)).toBeInTheDocument();
  });

  it("is hidden in the centre once permission was decided", () => {
    stubNotification("granted");
    wrap(<BrowserNotificationControl compact />);

    expect(screen.queryByText(/Browser notifications/)).not.toBeInTheDocument();
  });

  it("updates the badge and shows a system notification only in the background", () => {
    const { shown } = stubNotification("granted");
    const client = newClient();
    const navigate = vi.fn();
    hidden(true);

    handleNotificationEvent(client, navigate, created(true));

    expect(client.getQueryData(notificationKeys.unread())).toEqual({ unread_count: 4 });
    expect(shown).toHaveLength(1);
    expect(shown[0]?.title).toBe("New message from Bob Cruz");
    expect(shown[0]?.options?.tag).toBe("n-9");
    expect(shown[0]?.options?.body).toBeUndefined(); // the server sent no preview
    vi.spyOn(window, "focus").mockImplementation(() => undefined);
    shown[0]?.onclick?.();
    expect(navigate).toHaveBeenCalledWith("/messages/c-1");
  });

  it.each([
    ["the tab is visible", "granted", false, true],
    [
      "the server did not flag it for the browser (preference or quiet hours)",
      "granted",
      true,
      false,
    ],
    ["permission is not granted", "default", true, true],
    ["permission is denied", "denied", true, true],
  ] as const)("shows nothing when %s", (_why, permission, isHidden, flagged) => {
    const { shown } = stubNotification(permission);
    const client = newClient();
    hidden(isHidden);

    handleNotificationEvent(client, vi.fn(), created(flagged));

    expect(shown).toHaveLength(0);
    expect(client.getQueryData(notificationKeys.unread())).toEqual({ unread_count: 4 });
  });

  it("ignores malformed and unrelated events", () => {
    const { shown } = stubNotification("granted");
    const client = newClient();
    hidden(true);

    handleNotificationEvent(client, vi.fn(), { type: "notification.created", data: { nope: 1 } });
    handleNotificationEvent(client, vi.fn(), { type: "message.created", data: {} });

    expect(shown).toHaveLength(0);
    expect(client.getQueryData(notificationKeys.unread())).toBeUndefined();
  });

  it("does not crash when the browser refuses to build a notification", () => {
    vi.stubGlobal(
      "Notification",
      Object.assign(
        function Broken() {
          throw new TypeError("Illegal constructor");
        },
        { permission: "granted" },
      ),
    );
    hidden(true);
    const client = newClient();

    expect(() => handleNotificationEvent(client, vi.fn(), created(true, 2))).not.toThrow();
    expect(client.getQueryData(notificationKeys.unread())).toEqual({ unread_count: 2 });
  });
});
