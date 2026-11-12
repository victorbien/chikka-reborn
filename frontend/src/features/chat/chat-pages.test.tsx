import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ConversationSummary, MessagePage, ServerMessage } from "@/features/chat/types";
import { fail, makeProfile, mockApi, ok, signedInRoutes, type MockHandler } from "@/test/api-mock";
import { FakeWebSocket } from "@/test/fake-websocket";
import { renderApp } from "@/test/render-app";

const ME = makeProfile().id;
const THEM = "00000000-0000-4000-8000-0000000000b2";
const BASE = "/api/v1/conversations";
const CONVERSATION = `${BASE}/k-1`;

function message(seq: number, overrides: Partial<ServerMessage> = {}): ServerMessage {
  const mine = overrides.is_mine ?? false;
  return {
    id: `m-${seq}`,
    conversation_id: "k-1",
    seq,
    sender_user_id: mine ? ME : THEM,
    is_mine: mine,
    body: `Message ${seq}`,
    attachments: [],
    created_at: new Date(Date.now() - (10 - seq) * 60_000).toISOString(),
    edited_at: null,
    client_message_id: mine ? `client-${seq}` : null,
    status: mine ? "sent" : null,
    status_version: mine ? 1 : null,
    delivered_at: null,
    read_at: null,
    ...overrides,
  };
}

function summary(overrides: Partial<ConversationSummary> = {}): ConversationSummary {
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

function page(messages: ServerMessage[], overrides: Partial<MessagePage> = {}): MessagePage {
  return { messages, has_more_before: false, last_read_seq: 0, peer_read_seq: null, ...overrides };
}

function listOf(items: ConversationSummary[]): MockHandler {
  return {
    status: 200,
    body: {
      data: items,
      pagination: { total: items.length, page: 1, page_size: 30, has_next: false, has_prev: false },
      request_id: "req-test",
    },
  };
}

function chatRoutes(extra: Record<string, MockHandler> = {}): Record<string, MockHandler> {
  return {
    ...signedInRoutes(),
    [`GET ${BASE}`]: listOf([summary()]),
    [`GET ${BASE}/unread`]: ok({ unread_messages: 0, unread_conversations: 0 }),
    [`GET ${CONVERSATION}`]: ok(summary()),
    [`GET ${CONVERSATION}/messages`]: ok(page([])),
    [`POST ${CONVERSATION}/read`]: ok({
      conversation_id: "k-1",
      last_read_seq: 0,
      unread_count: 0,
    }),
    ...extra,
  };
}

/** Wait for the app's socket, answer its auth frame, and return it. */
async function connectedSocket(): Promise<FakeWebSocket> {
  await waitFor(() => expect(FakeWebSocket.latest()).toBeDefined());
  const socket = FakeWebSocket.latest() as FakeWebSocket;
  socket.ready();
  expect(socket.sent[0]).toEqual({ type: "auth", token: "access-1" });
  return socket;
}

function thread(): HTMLElement {
  return screen.getByRole("list", { name: "Messages with Juan dela Cruz" });
}

describe("conversation view", () => {
  it("shows the header, history with sender, time, date separators and status", async () => {
    const api = mockApi(
      chatRoutes({
        [`GET ${CONVERSATION}/messages`]: ok(
          page(
            [
              message(1, { created_at: "2026-11-10T09:00:00Z" }),
              message(2, { is_mine: true, status: "delivered", status_version: 2 }),
              message(3),
            ],
            { last_read_seq: 2 },
          ),
        ),
      }),
    );
    renderApp("/messages/k-1");
    expect(await screen.findByRole("heading", { name: "Juan dela Cruz" })).toBeInTheDocument();
    expect(screen.getByText("@juan_dc")).toBeInTheDocument();
    const list = await waitFor(thread);
    expect(within(list).getByText("Message 1")).toBeInTheDocument();
    expect(within(list).getByText("Today")).toBeInTheDocument();
    expect(within(list).getAllByRole("separator").length).toBeGreaterThanOrEqual(2);
    // Only messages after the read position are "new".
    expect(within(list).getByText("New messages")).toBeInTheDocument();
    expect(within(list).getByText("Delivered")).toBeInTheDocument();
    expect(within(list).getAllByRole("article", { name: /Juan dela Cruz, / })).toHaveLength(2);
    expect(within(list).getByRole("article", { name: /^You, / })).toBeInTheDocument();
    // Opening the conversation reports it read up to the newest message.
    await waitFor(() => expect(api.callsTo("POST", `${CONVERSATION}/read`)).toHaveLength(1));
    expect(api.callsTo("POST", `${CONVERSATION}/read`)[0]?.body).toEqual({ up_to_seq: 3 });
  });

  it("shows an empty state and focuses the composer", async () => {
    mockApi(chatRoutes());
    renderApp("/messages/k-1");
    expect(await screen.findByText("No messages yet")).toBeInTheDocument();
    expect(screen.getByText("Say hello to Juan dela Cruz.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Message")).toHaveFocus());
  });

  it("explains why sending is off", async () => {
    mockApi(
      chatRoutes({
        [`GET ${CONVERSATION}`]: ok(
          summary({ can_send: false, cannot_send_reason: "You blocked this person." }),
        ),
      }),
    );
    renderApp("/messages/k-1");
    expect(await screen.findByText("You blocked this person.")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toBeDisabled();
  });

  it("shows a readable error for a conversation you cannot open", async () => {
    mockApi(
      chatRoutes({ [`GET ${CONVERSATION}`]: fail(404, "not_found", "Conversation not found.") }),
    );
    renderApp("/messages/k-1");
    expect(await screen.findByRole("alert")).toHaveTextContent("Conversation not found.");
  });
});

describe("sending", () => {
  it("sends with Enter, shows Sending then Sent, and keeps Shift+Enter for new lines", async () => {
    let release: (() => void) | undefined;
    const api = mockApi(
      chatRoutes({
        [`POST ${CONVERSATION}/messages`]: (request) =>
          new Promise((resolve) => {
            const body = request.body as { client_message_id: string; body: string };
            release = () =>
              resolve({
                status: 201,
                body: {
                  data: message(1, {
                    is_mine: true,
                    body: body.body,
                    client_message_id: body.client_message_id,
                  }),
                  request_id: "r",
                },
              });
          }),
      }),
    );
    const user = userEvent.setup();
    renderApp("/messages/k-1");
    const box = await screen.findByLabelText("Message");
    await user.type(box, "Line one{Shift>}{Enter}{/Shift}line two");
    expect(api.callsTo("POST", `${CONVERSATION}/messages`)).toHaveLength(0);
    expect(box).toHaveValue("Line one\nline two");
    await user.keyboard("{Enter}");

    // Optimistic: visible at once as "Sending", and the box is cleared.
    expect(await within(thread()).findByText("Sending")).toBeInTheDocument();
    expect(box).toHaveValue("");
    const sent = api.callsTo("POST", `${CONVERSATION}/messages`)[0]?.body as Record<string, string>;
    expect(sent.body).toBe("Line one\nline two");
    expect(sent.client_message_id).toMatch(/^[0-9a-f-]{36}$/);

    release?.();
    expect(await within(thread()).findByText("Sent")).toBeInTheDocument();
    expect(within(thread()).getAllByRole("article")).toHaveLength(1);
  });

  it("marks a failed send and retries with the same client id", async () => {
    let attempts = 0;
    const api = mockApi(
      chatRoutes({
        [`POST ${CONVERSATION}/messages`]: (request) => {
          attempts += 1;
          const body = request.body as { client_message_id: string; body: string };
          return attempts === 1
            ? fail(503, "service_unavailable", "Messaging is unavailable. Try again.")
            : {
                status: 201,
                body: {
                  data: message(1, {
                    is_mine: true,
                    body: body.body,
                    client_message_id: body.client_message_id,
                  }),
                  request_id: "r",
                },
              };
        },
      }),
    );
    const user = userEvent.setup();
    renderApp("/messages/k-1");
    await user.type(await screen.findByLabelText("Message"), "Are you there?{Enter}");
    expect(await within(thread()).findByText("Failed")).toBeInTheDocument();
    // A readable reason is shown with the retry (the app words server failures itself).
    expect(within(thread()).getByRole("alert")).toHaveTextContent(/.+/);

    await user.click(within(thread()).getByRole("button", { name: "Try again" }));
    expect(await within(thread()).findByText("Sent")).toBeInTheDocument();
    const calls = api.callsTo("POST", `${CONVERSATION}/messages`);
    expect(calls).toHaveLength(2);
    const ids = calls.map((c) => (c.body as { client_message_id: string }).client_message_id);
    expect(ids[0]).toBe(ids[1]);
    expect(within(thread()).getAllByRole("article")).toHaveLength(1);
  });

  it("does not send blank messages and counts characters near the limit", async () => {
    const api = mockApi(chatRoutes());
    const user = userEvent.setup();
    renderApp("/messages/k-1");
    const box = await screen.findByLabelText("Message");
    await user.type(box, "   {Enter}");
    expect(api.callsTo("POST", `${CONVERSATION}/messages`)).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();

    await user.clear(box);
    await user.click(box);
    await user.paste("😀".repeat(2001));
    expect(screen.getByText(/2001\/2000 characters/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });

  it("inserts emoji from a keyboard-accessible picker", async () => {
    mockApi(chatRoutes());
    const user = userEvent.setup();
    renderApp("/messages/k-1");
    const box = await screen.findByLabelText("Message");
    await user.type(box, "Salamat ");
    await user.click(screen.getByRole("button", { name: "Insert emoji" }));
    const picker = screen.getByRole("group", { name: "Emoji" });
    expect(within(picker).getByRole("button", { name: "grinning face" })).toHaveFocus();
    await user.keyboard("{ArrowRight}{Enter}");
    await waitFor(() => expect(box).toHaveValue("Salamat 😂"));
    expect(screen.queryByRole("group", { name: "Emoji" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Insert emoji" }));
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Insert emoji" })).toHaveFocus();
  });

  it("uploads an attachment and sends it with the message", async () => {
    const attachment = {
      id: "a-1",
      file_name: "photo.png",
      content_type: "image/png",
      size_bytes: 2048,
      url: "https://storage.test/photo.png",
    };
    const api = mockApi(
      chatRoutes({
        [`POST ${CONVERSATION}/attachments`]: {
          status: 201,
          body: { data: attachment, request_id: "r" },
        },
        [`POST ${CONVERSATION}/messages`]: (request) => ({
          status: 201,
          body: {
            data: message(1, {
              is_mine: true,
              body: null,
              attachments: [attachment],
              client_message_id: (request.body as { client_message_id: string }).client_message_id,
            }),
            request_id: "r",
          },
        }),
      }),
    );
    const user = userEvent.setup();
    const { container } = renderApp("/messages/k-1");
    await screen.findByLabelText("Message");
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["png"], "photo.png", { type: "image/png" }));
    const files = await screen.findByRole("list", { name: "Files to send" });
    expect(within(files).getByText("photo.png")).toBeInTheDocument();

    // A photo with no text can be sent.
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(api.callsTo("POST", `${CONVERSATION}/messages`)).toHaveLength(1));
    expect(api.callsTo("POST", `${CONVERSATION}/messages`)[0]?.body).toMatchObject({
      attachment_ids: ["a-1"],
    });
    expect(await within(thread()).findByRole("img", { name: "photo.png" })).toBeInTheDocument();
  });

  it("rejects disallowed files before uploading", async () => {
    const api = mockApi(chatRoutes());
    const user = userEvent.setup({ applyAccept: false });
    const { container } = renderApp("/messages/k-1");
    await screen.findByLabelText("Message");
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["exe"], "setup.exe", { type: "application/x-msdownload" }));
    expect(await screen.findByText(/setup\.exe: use a JPEG/)).toBeInTheDocument();
    expect(api.callsTo("POST", `${CONVERSATION}/attachments`)).toHaveLength(0);
  });
});

describe("real time", () => {
  it("receives a pushed message once, announces it and acknowledges delivery", async () => {
    mockApi(chatRoutes({ [`GET ${CONVERSATION}/messages`]: ok(page([message(1)])) }));
    renderApp("/messages/k-1");
    await waitFor(thread);
    const socket = await connectedSocket();

    const pushed = { type: "message.created", event_id: "e-2", conversation_id: "k-1" };
    socket.push({ ...pushed, data: { message: message(2, { body: "Live hello" }) } });
    socket.push({ ...pushed, data: { message: message(2, { body: "Live hello" }) } });
    socket.push({
      ...pushed,
      event_id: "e-2b",
      data: { message: message(2, { body: "Live hello" }) },
    });

    expect(await within(thread()).findByText("Live hello")).toBeInTheDocument();
    expect(within(thread()).getAllByText("Live hello")).toHaveLength(1);
    expect(await screen.findByText("New message from Juan dela Cruz")).toBeInTheDocument();
    // "Delivered" means the app received it: an ack, never a "read".
    expect(socket.framesOfType("ack")).toContainEqual({ type: "ack", message_ids: ["m-2"] });
  });

  it("updates delivery state from the server and ignores older versions", async () => {
    mockApi(
      chatRoutes({
        [`GET ${CONVERSATION}/messages`]: ok(page([message(1, { is_mine: true })])),
      }),
    );
    renderApp("/messages/k-1");
    expect(await within(await waitFor(thread)).findByText("Sent")).toBeInTheDocument();
    const socket = await connectedSocket();
    const change = {
      message_id: "m-1",
      conversation_id: "k-1",
      delivered_at: "2026-11-12T08:00:00Z",
      read_at: null,
    };
    socket.push({
      type: "message.status_changed",
      event_id: "s-1",
      conversation_id: "k-1",
      data: { ...change, status: "delivered", status_version: 3 },
    });
    expect(await within(thread()).findByText("Delivered")).toBeInTheDocument();
    socket.push({
      type: "message.status_changed",
      event_id: "s-0",
      conversation_id: "k-1",
      data: { ...change, status: "sent", status_version: 2 },
    });
    expect(within(thread()).getByText("Delivered")).toBeInTheDocument();
  });

  it("shows the other person typing, then clears it", async () => {
    mockApi(chatRoutes());
    renderApp("/messages/k-1");
    await screen.findByText("No messages yet");
    const socket = await connectedSocket();
    socket.push({
      type: "typing",
      event_id: "t-1",
      conversation_id: "k-1",
      data: { user_id: THEM },
    });
    expect(await screen.findByText("Juan dela Cruz is typing…")).toBeInTheDocument();
    await waitFor(
      () => expect(screen.queryByText("Juan dela Cruz is typing…")).not.toBeInTheDocument(),
      {
        timeout: 5000,
      },
    );
  });

  it("sends a throttled typing signal while composing", async () => {
    mockApi(chatRoutes());
    const user = userEvent.setup();
    renderApp("/messages/k-1");
    const socket = await connectedSocket();
    await user.type(await screen.findByLabelText("Message"), "hello there");
    expect(socket.framesOfType("typing")).toEqual([{ type: "typing", conversation_id: "k-1" }]);
  });

  it("shows reconnecting, then catches up on missed messages without duplicates", async () => {
    vi.spyOn(Math, "random").mockReturnValue(0); // reconnect immediately
    let loads = 0;
    mockApi(
      chatRoutes({
        [`GET ${CONVERSATION}/messages`]: () => {
          loads += 1;
          return ok(
            page(loads === 1 ? [message(1)] : [message(1), message(2, { body: "Missed one" })]),
          );
        },
      }),
    );
    renderApp("/messages/k-1");
    await waitFor(thread);
    const first = await connectedSocket();
    first.serverClose(1006);
    expect(await screen.findByText(/Reconnecting/)).toBeInTheDocument();

    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(1));
    (FakeWebSocket.latest() as FakeWebSocket).ready();
    expect(await within(thread()).findByText("Missed one")).toBeInTheDocument();
    expect(within(thread()).getAllByText("Message 1")).toHaveLength(1);
    await waitFor(() => expect(screen.queryByText(/Reconnecting/)).not.toBeInTheDocument());
  });

  it("repairs a gap in sequence numbers from the server", async () => {
    let loads = 0;
    const api = mockApi(
      chatRoutes({
        [`GET ${CONVERSATION}/messages`]: () => {
          loads += 1;
          // First load and the resync on connect: only message 1 exists so far.
          return ok(page(loads <= 2 ? [message(1)] : [message(1), message(2), message(3)]));
        },
      }),
    );
    renderApp("/messages/k-1");
    await waitFor(thread);
    const socket = await connectedSocket();
    await waitFor(() => expect(loads).toBe(2));
    const before = api.callsTo("GET", `${CONVERSATION}/messages`).length;
    socket.push({
      type: "message.created",
      event_id: "e-3",
      conversation_id: "k-1",
      data: { message: message(3) },
    });
    expect(await within(thread()).findByText("Message 2")).toBeInTheDocument();
    expect(api.callsTo("GET", `${CONVERSATION}/messages`).length).toBeGreaterThan(before);
  });
});

describe("conversation list", () => {
  it("lists conversations with previews and unread badges, and searches", async () => {
    const api = mockApi(
      chatRoutes({
        [`GET ${BASE}`]: listOf([
          summary({
            unread_count: 2,
            last_message_at: new Date().toISOString(),
            last_message: {
              id: "m-9",
              seq: 9,
              is_mine: false,
              preview: "See you later",
              has_attachments: false,
              created_at: new Date().toISOString(),
              status: null,
            },
          }),
        ]),
      }),
    );
    const user = userEvent.setup();
    renderApp("/messages");
    const nav = await screen.findByRole("navigation", { name: "Conversations" });
    expect(await within(nav).findByText("See you later")).toBeInTheDocument();
    expect(within(nav).getByText("2 unread messages")).toBeInTheDocument();

    await user.type(within(nav).getByLabelText("Search conversations"), "juan");
    await waitFor(() =>
      expect(api.callsTo("GET", BASE).some((c) => c.search.includes("q=juan"))).toBe(true),
    );
  });

  it("shows archived conversations and an empty inbox", async () => {
    const api = mockApi(chatRoutes({ [`GET ${BASE}`]: listOf([]) }));
    const user = userEvent.setup();
    renderApp("/messages");
    expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Archived" }));
    expect(await screen.findByText("Nothing archived")).toBeInTheDocument();
    expect(api.callsTo("GET", BASE).some((c) => c.search.includes("archived=true"))).toBe(true);
  });

  it("archives the open conversation", async () => {
    const api = mockApi(
      chatRoutes({ [`PATCH ${CONVERSATION}`]: ok(summary({ is_archived: true })) }),
    );
    const user = userEvent.setup();
    renderApp("/messages/k-1");
    await user.click(await screen.findByRole("button", { name: "Archive" }));
    await waitFor(() => expect(api.callsTo("PATCH", CONVERSATION)).toHaveLength(1));
    expect(api.callsTo("PATCH", CONVERSATION)[0]?.body).toEqual({ is_archived: true });
    expect(await screen.findByRole("button", { name: "Unarchive" })).toBeInTheDocument();
  });

  it("opens a conversation with a contact from /messages/new", async () => {
    const api = mockApi(chatRoutes({ [`POST ${BASE}`]: ok(summary()) }));
    const { router } = renderApp(`/messages/new?user=${THEM}`);
    await waitFor(() => expect(router.state.location.pathname).toBe("/messages/k-1"));
    expect(api.callsTo("POST", BASE)[0]?.body).toEqual({ user_id: THEM });
  });

  it("explains when the person is not a contact", async () => {
    mockApi(
      chatRoutes({
        [`POST ${BASE}`]: fail(403, "not_a_contact", "You can only message your contacts."),
      }),
    );
    renderApp(`/messages/new?user=${THEM}`);
    expect(await screen.findByText("You can only message your contacts.")).toBeInTheDocument();
  });
});
