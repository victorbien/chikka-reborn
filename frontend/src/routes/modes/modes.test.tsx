import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ConversationSummary } from "@/features/chat/types";
import type { ContactSummary } from "@/features/contacts/types";
import { DISPLAY_MODE_STORAGE_KEY } from "@/lib/display-mode";
import { fail, makeProfile, mockApi, ok, signedInRoutes, type MockHandler } from "@/test/api-mock";
import { renderApp } from "@/test/render-app";

const THEM = "00000000-0000-4000-8000-0000000000b2";
const CONVERSATIONS = "/api/v1/conversations";
const CONTACTS = "/api/v1/contacts";
const ME = "/api/v1/users/me";

function stubViewport(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query);
    return {
      matches: min ? width >= Number(min[1]) : false,
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    };
  });
}

function contact(overrides: Partial<ContactSummary> = {}): ContactSummary {
  return {
    id: "c-1",
    contact_type: "chikka",
    user_id: THEM,
    username: "juan_dc",
    display_name: "Juan dela Cruz",
    nickname: "Kuya Juan",
    avatar_url: null,
    status_message: "At work",
    presence: "online",
    last_seen_at: null,
    is_favourite: false,
    group_ids: [],
    masked_phone: null,
    ...overrides,
  };
}

function conversation(overrides: Partial<ConversationSummary> = {}): ConversationSummary {
  return {
    id: "k-1",
    conversation_type: "chikka",
    participant: {
      user_id: THEM,
      username: "juan_dc",
      display_name: "Juan dela Cruz",
      avatar_url: null,
      presence: "online",
      is_contact: true,
    },
    last_message: null,
    last_message_at: null,
    unread_count: 0,
    is_archived: false,
    is_muted: false,
    can_send: true,
    cannot_send_reason: null,
    ...overrides,
  };
}

function paged<T>(items: T[]): MockHandler {
  return {
    status: 200,
    body: {
      data: items,
      pagination: { total: items.length, page: 1, page_size: 50, has_next: false, has_prev: false },
      request_id: "req-test",
    },
  };
}

function routes(extra: Record<string, MockHandler> = {}): Record<string, MockHandler> {
  return {
    ...signedInRoutes(),
    [CONVERSATIONS]: paged([conversation({ unread_count: 2 })]),
    [`GET ${CONVERSATIONS}`]: paged([conversation({ unread_count: 2 })]),
    [`GET ${CONVERSATIONS}/unread`]: ok({ unread_messages: 2, unread_conversations: 1 }),
    [`GET ${CONVERSATIONS}/k-1`]: ok(conversation()),
    [`GET ${CONVERSATIONS}/k-1/messages`]: ok({
      messages: [],
      has_more_before: false,
      last_read_seq: 0,
      peer_read_seq: null,
    }),
    [`GET ${CONTACTS}`]: paged([
      contact(),
      contact({
        id: "c-2",
        user_id: "u-2",
        display_name: "Ana Reyes",
        nickname: null,
        presence: "offline",
        status_message: null,
      }),
    ]),
    [`GET ${CONTACTS}/groups`]: ok([]),
    [`GET ${CONTACTS}/requests`]: paged([]),
    "GET /api/v1/ai/status": ok({
      available: true,
      enabled: true,
      simulated: true,
      model_id: "test-model",
      languages: [{ code: "en", name: "English" }],
      max_text_chars: 1600,
    }),
    ...extra,
  };
}

const CLASSIC_PROFILE: Record<string, MockHandler> = {
  "GET /api/v1/users/me": ok(makeProfile({ ui_mode: "classic" })),
};

function classicRoutes(extra: Record<string, MockHandler> = {}): Record<string, MockHandler> {
  return routes({ ...CLASSIC_PROFILE, ...extra });
}

describe("Classic mode", () => {
  it("shows a compact buddy list with nicknames, presence groups and unread indicators", async () => {
    stubViewport(1280);
    mockApi(classicRoutes());
    localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, "classic");
    renderApp("/messages");

    const online = await screen.findByRole("region", { name: "Online" });
    expect(within(online).getByText("Kuya Juan")).toBeInTheDocument();
    expect(within(online).getByText("2 unread messages")).toBeInTheDocument();
    const offline = screen.getByRole("region", { name: "Offline" });
    expect(within(offline).getByText("Ana Reyes")).toBeInTheDocument();
    expect(await screen.findByText(/1 online · 2 total/)).toBeInTheDocument();
    expect(screen.getByText("2 new")).toBeInTheDocument();
    expect(document.documentElement.dataset.mode).toBe("classic");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  });

  it("opens a chat window from a buddy and labels it with the nickname", async () => {
    stubViewport(1280);
    const api = mockApi(
      classicRoutes({
        [`POST ${CONVERSATIONS}`]: ok(conversation()),
        [`POST ${CONVERSATIONS}/k-1/read`]: ok({
          conversation_id: "k-1",
          last_read_seq: 0,
          unread_count: 0,
        }),
      }),
    );
    localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, "classic");
    const user = userEvent.setup();
    renderApp("/messages");

    await user.click(await screen.findByRole("button", { name: /Kuya Juan/ }));
    expect(await screen.findByRole("heading", { name: /Kuya Juan/, level: 2 })).toBeInTheDocument();
    expect(api.callsTo("POST", CONVERSATIONS)[0]?.body).toEqual({ user_id: THEM });
  });

  it("moves between buddies with the arrow keys", async () => {
    stubViewport(1280);
    mockApi(classicRoutes());
    localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, "classic");
    const user = userEvent.setup();
    renderApp("/messages");

    const first = await screen.findByRole("button", { name: /Kuya Juan/ });
    first.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("button", { name: "Offline (1)" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("button", { name: /Ana Reyes/ })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("button", { name: "Online (1)" })).toHaveFocus();
  });

  it("focuses the buddy search with the / key and filters the list", async () => {
    stubViewport(1280);
    mockApi(classicRoutes());
    localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, "classic");
    const user = userEvent.setup();
    renderApp("/messages");

    await screen.findByText("Kuya Juan");
    await user.keyboard("/");
    const box = screen.getByRole("searchbox", { name: "Search buddies" });
    expect(box).toHaveFocus();
    await user.type(box, "zzz");
    expect(await screen.findByText("No buddies match “zzz”.")).toBeInTheDocument();
  });

  it("explains an empty buddy list", async () => {
    stubViewport(1280);
    mockApi(classicRoutes({ [`GET ${CONTACTS}`]: paged<ContactSummary>([]) }));
    localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, "classic");
    renderApp("/messages");
    expect(await screen.findByText("Your buddy list is empty")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add buddies" })).toBeInTheDocument();
  });

  it("shows only the chat window on a phone once a chat is open", async () => {
    stubViewport(375);
    mockApi(classicRoutes());
    localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, "classic");
    renderApp("/messages/k-1");
    expect(await screen.findByRole("link", { name: "Back to conversations" })).toBeInTheDocument();
    const buddyList = screen.getByRole("region", { name: "Buddy list", hidden: true });
    expect(buddyList).toHaveClass("hidden");
    expect(buddyList).toHaveClass("md:flex");
  });
});

describe("Modern mode", () => {
  it("shows three columns on a desktop: chats, conversation, details and AI", async () => {
    stubViewport(1440);
    mockApi(routes());
    renderApp("/messages/k-1");

    expect(await screen.findByRole("tab", { name: "Chats" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "People" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Juan dela Cruz", level: 2 }),
    ).toBeInTheDocument();
    const side = await screen.findByRole("complementary", { name: "Conversation tools" });
    expect(within(side).getByRole("heading", { name: "Conversation details" })).toBeInTheDocument();
    expect(within(side).getByText(/No SMS is sent and no credits are used/)).toBeInTheDocument();
    expect(within(side).getByRole("region", { name: "AI assistant" })).toBeInTheDocument();
    // The assistant lives in the side column, so the composer does not repeat its button.
    expect(screen.getAllByText("AI assistant")).toHaveLength(1);
  });

  it("keeps the AI assistant in the composer on small screens", async () => {
    stubViewport(390);
    mockApi(routes());
    renderApp("/messages/k-1");
    expect(await screen.findByRole("button", { name: "AI assistant" })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Conversation tools" })).toBeNull();
  });

  it("puts an AI suggestion in the message box without sending it", async () => {
    stubViewport(1440);
    const api = mockApi(
      routes({
        "POST /api/v1/ai/suggest-replies": ok({
          suggestions: ["Sige, see you there!"],
          assistance_id: "22222222-2222-4222-8222-222222222222",
          model_id: "test-model",
          latency_ms: 5,
          simulated: true,
          message: null,
        }),
      }),
    );
    const user = userEvent.setup();
    renderApp("/messages/k-1");
    const side = await screen.findByRole("complementary", { name: "Conversation tools" });
    await user.click(await within(side).findByRole("button", { name: "Ask the assistant" }));
    await user.click(await within(side).findByRole("button", { name: "Use" }));

    expect(await screen.findByLabelText("Message")).toHaveValue("Sige, see you there!");
    expect(await screen.findByText("AI-assisted")).toBeInTheDocument();
    expect(api.callsTo("POST", `${CONVERSATIONS}/k-1/messages`)).toHaveLength(0);
  });

  it("opens a conversation from the People tab", async () => {
    stubViewport(1440);
    const api = mockApi(routes({ [`POST ${CONVERSATIONS}`]: ok(conversation()) }));
    const user = userEvent.setup();
    renderApp("/messages");

    await user.click(await screen.findByRole("tab", { name: "People" }));
    await user.type(await screen.findByLabelText("Search contacts"), "Ana");
    expect(screen.queryByText("Juan dela Cruz")).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText("Search contacts"));
    await user.click(await screen.findByRole("button", { name: /Juan dela Cruz/ }));
    await waitFor(() => expect(api.callsTo("POST", CONVERSATIONS)).toHaveLength(1));
    expect(
      await screen.findByRole("heading", { name: "Juan dela Cruz", level: 2 }),
    ).toBeInTheDocument();
  });

  it("explains an empty inbox", async () => {
    stubViewport(1440);
    mockApi(routes({ [`GET ${CONVERSATIONS}`]: paged<ConversationSummary>([]) }));
    renderApp("/messages");
    expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
    expect(screen.getByText("Choose a conversation")).toBeInTheDocument();
  });
});

describe("switching modes", () => {
  it("saves the choice to the profile and keeps the same data on screen", async () => {
    stubViewport(1280);
    const api = mockApi(
      routes({
        [`PATCH ${ME}`]: ok(makeProfile({ ui_mode: "classic" })),
      }),
    );
    const user = userEvent.setup();
    renderApp("/messages/k-1");
    await screen.findByRole("heading", { name: "Juan dela Cruz", level: 2 });
    const listCallsBefore = api.callsTo("GET", CONVERSATIONS).length;

    await user.click(screen.getByRole("button", { name: "Switch to Classic mode" }));
    await waitFor(() => expect(document.documentElement.dataset.mode).toBe("classic"));
    await waitFor(() => expect(api.callsTo("PATCH", ME)).toHaveLength(1));
    expect(api.callsTo("PATCH", ME)[0]?.body).toEqual({ ui_mode: "classic" });
    expect(localStorage.getItem(DISPLAY_MODE_STORAGE_KEY)).toBe("classic");

    // Same conversation, same contact, no messages sent, nothing else changed on the profile.
    expect(
      await screen.findByRole("heading", { name: /Juan dela Cruz|Kuya Juan/, level: 2 }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Online" })).toBeInTheDocument();
    expect(api.callsTo("POST", `${CONVERSATIONS}/k-1/messages`)).toHaveLength(0);
    expect(api.callsTo("GET", CONVERSATIONS).length).toBeGreaterThanOrEqual(listCallsBefore);
    expect(screen.getByRole("button", { name: "Switch to Modern mode" })).toBeInTheDocument();
  });

  it("goes back to the previous mode when saving fails", async () => {
    stubViewport(1280);
    mockApi(routes({ [`PATCH ${ME}`]: fail(500, "internal_error", "Could not save.") }));
    const user = userEvent.setup();
    renderApp("/messages");
    await screen.findByRole("tab", { name: "Chats" });

    await user.click(screen.getByRole("button", { name: "Switch to Classic mode" }));
    await waitFor(() => expect(document.documentElement.dataset.mode).toBe("modern"));
    expect(
      await screen.findByText("Your interface choice could not be saved."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Switch to Classic mode" })).toBeInTheDocument();
  });

  it("follows the saved profile preference over this device's stored one", async () => {
    stubViewport(1280);
    mockApi(routes({ "GET /api/v1/users/me": ok(makeProfile({ ui_mode: "classic" })) }));
    localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, "modern");
    renderApp("/messages");
    await waitFor(() => expect(document.documentElement.dataset.mode).toBe("classic"));
    expect(await screen.findByRole("region", { name: "Buddy list" })).toBeInTheDocument();
  });

  it("can be changed from settings too", async () => {
    stubViewport(1280);
    const api = mockApi(routes({ [`PATCH ${ME}`]: ok(makeProfile({ ui_mode: "classic" })) }));
    const user = userEvent.setup();
    renderApp("/settings/profile");
    await user.click(await screen.findByRole("radio", { name: /Classic/ }));
    await waitFor(() => expect(api.callsTo("PATCH", ME)).toHaveLength(1));
    expect(api.callsTo("PATCH", ME)[0]?.body).toEqual({ ui_mode: "classic" });
  });
});

describe("conversation controls", () => {
  it("asks before archiving and does nothing when cancelled", async () => {
    stubViewport(1280);
    const api = mockApi(routes());
    const user = userEvent.setup();
    renderApp("/messages/k-1");

    await user.click(await screen.findByRole("button", { name: "Archive" }));
    const dialog = await screen.findByRole("dialog", { name: "Archive this conversation?" });
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(api.callsTo("PATCH", `${CONVERSATIONS}/k-1`)).toHaveLength(0);
  });

  it("shows the archive tooltip on keyboard focus", async () => {
    stubViewport(1280);
    mockApi(routes());
    const user = userEvent.setup();
    renderApp("/messages/k-1");
    await screen.findByRole("button", { name: "Archive" });
    await user.tab();
    const archive = screen.getByRole("button", { name: "Archive" });
    archive.focus();
    expect(await screen.findByRole("tooltip")).toHaveTextContent(/Hide this conversation/);
  });
});
