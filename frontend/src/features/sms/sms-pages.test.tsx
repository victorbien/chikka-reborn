import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Country, Quote, SmsConversation, SmsMessage, SmsThread } from "@/features/sms/types";
import { fail, mockApi, ok, signedInRoutes, type MockHandler } from "@/test/api-mock";
import { FakeWebSocket } from "@/test/fake-websocket";
import { renderApp } from "@/test/render-app";

const BASE = "/api/v1/sms";
const CONVERSATION = "c-1";

function status(overrides = {}): MockHandler {
  return ok({
    mode: "simulation",
    provider: "mock",
    is_simulated: true,
    outbound_paused: false,
    sender_verified: true,
    notice: "Simulation mode: no real SMS is sent and nothing costs money.",
    ...overrides,
  });
}

function country(overrides: Partial<Country> = {}): Country {
  return {
    country_code: "PH",
    country_name: "Philippines",
    dial_code: 63,
    availability: "simulation_only",
    unavailable_reason: null,
    outbound: "requires_verification",
    replies: "unverified",
    registered_sender_required: true,
    registered_sender_status: "not_registered",
    content_restrictions: null,
    consent_required: true,
    credits_per_segment: null,
    max_segments: 10,
    verified: false,
    notes: null,
    ...overrides,
  };
}

function quote(overrides: Partial<Quote> = {}): Quote {
  return {
    recipient: {
      masked_phone: "+63****4567",
      country_code: "PH",
      country_name: "Philippines",
      number_type: "mobile",
      contact_id: null,
      display_name: null,
      conversation_id: null,
    },
    mode: "simulation",
    is_simulated: true,
    availability: "simulation_only",
    replies: "unverified",
    warnings: ["Simulation only: the route to Philippines is not verified for live SMS."],
    segment: {
      encoding: "gsm7",
      characters: 5,
      units: 5,
      segments: 1,
      per_segment: 160,
      remaining_in_segment: 155,
      max_segments: 10,
      too_long: false,
    },
    cost: { units: 100, credits: 1, source: "demo_default", estimated: true },
    consent: { required: true, granted: true, notice_version: "2026-11-01" },
    recipient_opted_out: false,
    blockers: [],
    can_send: true,
    ...overrides,
  };
}

function message(seq: number, overrides: Partial<SmsMessage> = {}): SmsMessage {
  const outbound = (overrides.direction ?? "outbound") === "outbound";
  return {
    id: `m-${seq}`,
    conversation_id: CONVERSATION,
    seq,
    direction: outbound ? "outbound" : "inbound",
    is_mine: outbound,
    body: `Text ${seq}`,
    status: outbound ? "accepted" : "received",
    status_version: 1,
    is_simulated: true,
    encoding: "gsm7",
    char_count: 6,
    segment_count: 1,
    created_at: "2026-11-12T10:00:00Z",
    client_message_id: outbound ? `k-${seq}` : null,
    delivery: {
      attempt_number: 1,
      provider: "mock",
      accepted_at: null,
      sent_at: null,
      delivered_at: null,
      next_attempt_at: null,
      confirmation: "pending",
    },
    failure: null,
    can_retry: false,
    attempt_count: 1,
    ...overrides,
  };
}

function conversation(overrides: Partial<SmsConversation> = {}): SmsConversation {
  return {
    id: CONVERSATION,
    masked_phone: "+63****4567",
    country_code: "PH",
    display_name: "Nanay",
    contact_id: "ct-1",
    last_message_preview: "Text 1",
    last_message_direction: "outbound",
    last_message_status: "accepted",
    last_message_at: "2026-11-12T10:00:00Z",
    last_is_simulated: true,
    unread_count: 0,
    is_archived: false,
    is_muted: false,
    replies: "unverified",
    ...overrides,
  };
}

function thread(messages: SmsMessage[]): SmsThread {
  return { messages, has_more_before: false, last_read_seq: 0 };
}

function routes(extra: Record<string, MockHandler> = {}): Record<string, MockHandler> {
  return {
    ...signedInRoutes(),
    [`GET ${BASE}/status`]: status(),
    [`GET ${BASE}/countries`]: ok([
      country(),
      country({ country_code: "US", country_name: "United States", dial_code: 1 }),
    ]),
    [`GET ${BASE}/conversations`]: {
      status: 200,
      body: {
        data: [conversation()],
        pagination: { total: 1, page: 1, page_size: 30, has_next: false, has_prev: false },
        request_id: "req-test",
      },
    },
    [`GET ${BASE}/conversations/${CONVERSATION}/messages`]: ok(thread([message(1)])),
    ...extra,
  };
}

async function connectedSocket(): Promise<FakeWebSocket> {
  await waitFor(() => expect(FakeWebSocket.latest()).toBeDefined());
  const socket = FakeWebSocket.latest() as FakeWebSocket;
  socket.ready();
  return socket;
}

describe("SMS conversation", () => {
  it("labels the mode and shows each message's channel, SIMULATED label and honest status", async () => {
    mockApi(routes());
    renderApp(`/sms/${CONVERSATION}`);
    const banner = await screen.findByText(/no real SMS is sent/);
    expect(banner).toBeInTheDocument();
    const list = await screen.findByRole("log", { name: "SMS messages" });
    expect(within(list).getByText("SMS out")).toBeInTheDocument();
    expect(within(list).getAllByText("SIMULATED").length).toBeGreaterThan(0);
    // Accepted by the provider is not delivered.
    expect(within(list).getByText("Accepted by provider")).toBeInTheDocument();
    expect(within(list).queryByText("Delivered")).not.toBeInTheDocument();
    expect(screen.getByText(/Replies may arrive but are not guaranteed/)).toBeInTheDocument();
    // The number is masked everywhere.
    expect(screen.getAllByText(/\+63\*\*\*\*4567/).length).toBeGreaterThan(0);
  });

  it("shows replies as SMS in, marks them read, and updates status from real-time events", async () => {
    const api = mockApi(
      routes({
        [`GET ${BASE}/conversations/${CONVERSATION}/messages`]: ok(
          thread([message(1), message(2, { direction: "inbound", body: "Okay sige anak." })]),
        ),
        [`POST ${BASE}/conversations/${CONVERSATION}/read`]: ok({
          conversation_id: CONVERSATION,
          last_read_seq: 2,
          unread_count: 0,
        }),
      }),
    );
    renderApp(`/sms/${CONVERSATION}`);
    const list = await screen.findByRole("log", { name: "SMS messages" });
    expect(within(list).getByText("Okay sige anak.")).toBeInTheDocument();
    expect(within(list).getByText("SMS in")).toBeInTheDocument();
    await waitFor(() =>
      expect(api.callsTo("POST", `${BASE}/conversations/${CONVERSATION}/read`)).toHaveLength(1),
    );

    const socket = await connectedSocket();
    // Connecting resyncs from REST; let that settle so it cannot overwrite the pushed update.
    await waitFor(() =>
      expect(api.callsTo("GET", `${BASE}/conversations/${CONVERSATION}/messages`)).toHaveLength(2),
    );
    await new Promise((resolve) => setTimeout(resolve, 20));
    socket.push({
      type: "sms.message.updated",
      event_id: "e1",
      conversation_id: CONVERSATION,
      data: {
        message: message(1, {
          status: "delivered",
          status_version: 2,
          delivery: {
            ...message(1).delivery!,
            delivered_at: "2026-11-12T10:00:06Z",
            confirmation: "confirmed",
          },
        }),
      },
    });
    await waitFor(() => expect(within(list).getByText("Delivered")).toBeInTheDocument());
    // A stale event never moves a status backwards.
    socket.push({
      type: "sms.message.updated",
      event_id: "e2",
      conversation_id: CONVERSATION,
      data: { message: message(1, { status: "accepted", status_version: 1 }) },
    });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(within(list).getByText("Delivered")).toBeInTheDocument();
  });

  it("explains a failure, warns when the outcome is unknown, and retries only after confirmation", async () => {
    const failed = message(1, {
      status: "failed",
      can_retry: true,
      failure: {
        code: "outcome_unknown",
        reason: "We couldn't confirm whether this message was sent.",
        is_permanent: true,
        may_have_been_delivered: true,
      },
    });
    const api = mockApi(
      routes({
        [`GET ${BASE}/conversations/${CONVERSATION}/messages`]: ok(thread([failed])),
        [`POST ${BASE}/messages/m-1/retry`]: {
          status: 202,
          body: { data: message(3, { status: "queued" }), request_id: "r" },
        },
      }),
    );
    const user = userEvent.setup();
    renderApp(`/sms/${CONVERSATION}`);
    const group = await screen.findByRole("group", { name: "Failure details" });
    expect(
      within(group).getByText(/couldn't confirm whether this message was sent/),
    ).toBeInTheDocument();
    expect(within(group).getByText(/may still have been delivered/)).toBeInTheDocument();

    await user.click(within(group).getByRole("button", { name: "Send again" }));
    expect(api.callsTo("POST", `${BASE}/messages/m-1/retry`)).toHaveLength(0);
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Send again" }));
    await waitFor(() => expect(api.callsTo("POST", `${BASE}/messages/m-1/retry`)).toHaveLength(1));
    const call = api.callsTo("POST", `${BASE}/messages/m-1/retry`)[0];
    expect(call?.body).toEqual({ confirmed: true });
    expect(call?.headers["Idempotency-Key"]).toMatch(/[0-9a-f-]{36}/);
  });
});

describe("composing an SMS", () => {
  it("shows segments, estimated cost and warnings, and only sends after the confirmation dialog", async () => {
    let sentBody: unknown;
    const api = mockApi(
      routes({
        [`POST ${BASE}/quote`]: (request) => {
          const body = request.body as { body: string };
          return ok(
            quote({
              segment: { ...quote().segment, characters: body.body.length },
            }),
          );
        },
        [`POST ${BASE}/messages`]: (request) => {
          sentBody = request.body;
          return {
            status: 202,
            body: {
              data: message(9, { conversation_id: CONVERSATION, status: "queued" }),
              request_id: "r",
            },
          };
        },
      }),
    );
    const user = userEvent.setup();
    renderApp("/sms/new");
    await user.type(await screen.findByLabelText("Mobile number"), "0917 123 4567");
    await user.type(screen.getByLabelText("Message"), "Hello");

    expect(
      await screen.findByText(
        /Estimated 1.00 credits \(nothing is charged in simulation, demo rate\)/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/not verified for live SMS/)).toBeInTheDocument();
    expect(screen.getByText(/not guaranteed/)).toBeInTheDocument();

    const review = screen.getByRole("button", { name: "Review and send" });
    await waitFor(() => expect(review).toBeEnabled());
    await user.click(review);
    expect(api.callsTo("POST", `${BASE}/messages`)).toHaveLength(0);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("SIMULATED")).toBeInTheDocument();
    expect(within(dialog).getByText("Hello")).toBeInTheDocument();
    expect(within(dialog).getByText(/\+63\*\*\*\*4567/)).toBeInTheDocument();
    expect(within(dialog).getByText(/no real SMS will be sent/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Send SMS" }));

    await waitFor(() => expect(api.callsTo("POST", `${BASE}/messages`)).toHaveLength(1));
    expect(sentBody).toEqual({
      to: "0917 123 4567",
      country_code: "PH",
      body: "Hello",
      confirmed: true,
    });
    expect(api.callsTo("POST", `${BASE}/messages`)[0]?.headers["Idempotency-Key"]).toMatch(
      /[0-9a-f-]{36}/,
    );
  });

  it("blocks sending until the sender confirms permission, then records it", async () => {
    let granted = false;
    const api = mockApi(
      routes({
        [`POST ${BASE}/quote`]: () =>
          ok(
            quote({
              consent: { required: true, granted, notice_version: "2026-11-01" },
              blockers: granted
                ? []
                : [{ code: "consent_required", message: "Confirm permission." }],
              can_send: granted,
            }),
          ),
        [`PUT ${BASE}/consents`]: () => {
          granted = true;
          return ok({ required: true, granted: true, notice_version: "2026-11-01" });
        },
      }),
    );
    const user = userEvent.setup();
    renderApp("/sms/new");
    await user.type(await screen.findByLabelText("Mobile number"), "0917 123 4567");
    await user.type(screen.getByLabelText("Message"), "Hello");
    const checkbox = await screen.findByRole("checkbox", { name: /permission to text them/ });
    expect(screen.getByRole("button", { name: "Review and send" })).toBeDisabled();
    await user.click(checkbox);
    await waitFor(() => expect(api.callsTo("PUT", `${BASE}/consents`)).toHaveLength(1));
    expect(api.callsTo("PUT", `${BASE}/consents`)[0]?.body).toEqual({
      to: "0917 123 4567",
      country_code: "PH",
      decision: "granted",
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Review and send" })).toBeEnabled(),
    );
  });

  it("shows why a destination is unavailable and never offers to send", async () => {
    mockApi(
      routes({
        [`POST ${BASE}/quote`]: ok(
          quote({
            availability: "unavailable",
            replies: "unsupported",
            blockers: [{ code: "country_unsupported", message: "SMS to Narnia is not supported." }],
            can_send: false,
          }),
        ),
      }),
    );
    const user = userEvent.setup();
    renderApp("/sms/new");
    await user.type(await screen.findByLabelText("Mobile number"), "0917 123 4567");
    await user.type(screen.getByLabelText("Message"), "Hello");
    expect(await screen.findByText("SMS to Narnia is not supported.")).toBeInTheDocument();
    expect(screen.getByText(/Replies are not supported for this destination/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review and send" })).toBeDisabled();
  });

  it("surfaces a server refusal inside the confirmation dialog and keeps the text", async () => {
    mockApi(
      routes({
        [`POST ${BASE}/quote`]: ok(quote()),
        [`POST ${BASE}/messages`]: fail(
          422,
          "recipient_opted_out",
          "This person has opted out of messages, so we can't send to this number.",
        ),
      }),
    );
    const user = userEvent.setup();
    renderApp("/sms/new");
    await user.type(await screen.findByLabelText("Mobile number"), "0917 123 4567");
    await user.type(screen.getByLabelText("Message"), "Hello");
    const review = screen.getByRole("button", { name: "Review and send" });
    await waitFor(() => expect(review).toBeEnabled());
    await user.click(review);
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Send SMS" }),
    );
    expect(await screen.findByText(/opted out of messages/)).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toHaveValue("Hello");
  });
});

describe("SMS conversation list and mode banner", () => {
  it("lists conversations with masked numbers, unread counts and the SIMULATED label", async () => {
    mockApi(
      routes({
        [`GET ${BASE}/conversations`]: {
          status: 200,
          body: {
            data: [conversation({ unread_count: 2 })],
            pagination: { total: 1, page: 1, page_size: 30, has_next: false, has_prev: false },
            request_id: "r",
          },
        },
      }),
    );
    renderApp("/sms");
    const link = await screen.findByRole("link", { name: /Nanay/ });
    expect(link).toHaveTextContent("+63****4567");
    expect(link).toHaveTextContent("2 unread");
    expect(link).toHaveTextContent("SIMULATED");
  });

  it("shows a live banner, a paused notice and the verify-your-number prompt", async () => {
    mockApi(
      routes({
        [`GET ${BASE}/status`]: status({
          mode: "live",
          provider: "twilio",
          is_simulated: false,
          outbound_paused: true,
          sender_verified: false,
          notice: "Live mode: messages are sent to real phones.",
        }),
      }),
    );
    renderApp("/sms");
    expect(await screen.findByText("LIVE")).toBeInTheDocument();
    expect(screen.getByText(/paused by an administrator/)).toBeInTheDocument();
    const banner = screen
      .getByText(/paused by an administrator/)
      .closest("[role=status]") as HTMLElement;
    expect(within(banner).getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("offers a next step when there are no conversations, and a retry on error", async () => {
    mockApi(
      routes({
        [`GET ${BASE}/conversations`]: fail(500, "internal_error", "boom"),
      }),
    );
    renderApp("/sms");
    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
