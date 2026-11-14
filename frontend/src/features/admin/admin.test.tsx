import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type {
  AdminUserDetail,
  AdminUserRow,
  AiMetrics,
  AuditLogRow,
  Dashboard,
  ProviderOverview,
  SmsMessageDetail,
  SmsMessageRow,
} from "@/features/admin/api";
import { fail, makeProfile, mockApi, ok, signedInRoutes, type MockHandler } from "@/test/api-mock";
import { renderApp } from "@/test/render-app";

const BASE = "/api/v1/admin";
const USER_ID = "11111111-1111-4111-8111-111111111111";
const MESSAGE_ID = "22222222-2222-4222-8222-222222222222";

function paged<T>(items: T[]): MockHandler {
  return {
    status: 200,
    body: {
      data: items,
      pagination: {
        total: items.length,
        page: 1,
        page_size: 30,
        has_next: false,
        has_prev: false,
      },
      request_id: "req-test",
    },
  };
}

const modeStats = (overrides: Partial<Dashboard["sms"]["live"]> = {}) => ({
  sent: 0,
  received: 0,
  delivered: 0,
  failed: 0,
  undelivered: 0,
  in_progress: 0,
  delivery_success_rate: null,
  ...overrides,
});

const dashboard: Dashboard = {
  generated_at: "2026-11-14T10:00:00Z",
  users: {
    total_registered: 42,
    active_accounts: 40,
    pending_verification: 1,
    suspended: 1,
    administrators: 2,
    active_last_24h: 7,
    active_last_7d: 20,
    active_last_30d: 31,
  },
  conversations: { total: 17, chikka: 12, sms: 5 },
  messages: { chikka_messages_sent: 230 },
  sms: {
    simulated: modeStats({
      sent: 9,
      received: 2,
      delivered: 6,
      failed: 2,
      delivery_success_rate: 0.75,
    }),
    live: modeStats(),
  },
  ai: {
    total_requests: 55,
    last_24h: 3,
    failed_requests: 4,
    input_tokens: 1000,
    output_tokens: 400,
  },
  credits: [
    {
      ledger_type: "demo",
      transactions: 12,
      units_granted: 500,
      units_deducted: 90,
      units_refunded: 10,
      units_adjusted: 0,
    },
  ],
};

const overview: ProviderOverview = {
  health: {
    health: "degraded",
    reasons: ["Some provider callbacks could not be processed."],
    mode: "simulation",
    running_provider: "mock",
    active_provider: "mock",
    credentials_configured: true,
    outbound_paused: false,
    dispatch_paused_by_configuration_error: false,
    queue_depth: 3,
    delivery_success_rate_24h: 0.75,
    webhook_failures_24h: 1,
    webhook_signature_rejections_24h: 0,
  },
  configuration: {
    app_env: "development",
    sms_provider_mode: "mock",
    sms_live_confirmed: false,
    sms_worker_enabled: true,
    ai_provider_mode: "mock",
    ai_provider_configured: true,
    email_provider_mode: "mock",
  },
  capabilities: [
    {
      country_code: "PH",
      country_name: "Philippines",
      outbound_support: "requires_verification",
      inbound_support: "requires_verification",
      registered_sender_required: true,
      registered_sender_status: "not_registered",
      verified: false,
    },
  ],
};

function userRow(overrides: Partial<AdminUserRow> = {}): AdminUserRow {
  return {
    id: USER_ID,
    username: "marites",
    display_name: "Marites Santos",
    masked_email: "m***@example.com",
    role: "user",
    status: "active",
    country_code: "PH",
    created_at: "2026-11-01T00:00:00Z",
    last_seen_at: "2026-11-13T00:00:00Z",
    suspended_at: null,
    ...overrides,
  };
}

function userDetail(overrides: Partial<AdminUserDetail> = {}): AdminUserDetail {
  return {
    ...userRow(),
    masked_verified_phone: "+63****4567",
    ai_enabled: true,
    deletion_requested_at: null,
    activity: {
      chikka_messages_sent: 5,
      sms_sent: 2,
      sms_received: 1,
      conversations: 3,
      ai_requests: 4,
      open_reports_against: 0,
      active_sessions: 1,
    },
    credits: [{ ledger_type: "demo", balance_units: 450, reserved_units: 0 }],
    ...overrides,
  };
}

const smsRow: SmsMessageRow = {
  id: MESSAGE_ID,
  direction: "outbound",
  status: "failed",
  is_simulated: true,
  created_at: "2026-11-14T09:00:00Z",
  masked_phone: "+12****0104",
  user_id: USER_ID,
  segment_count: 1,
  attempts: 2,
  provider_message_id: null,
  failure_class: "transient",
  failure_code: "retries_exhausted",
  failure_reason: "We couldn't reach the SMS provider after several tries.",
};

const smsDetail: SmsMessageDetail = {
  ...smsRow,
  attempts_history: [
    {
      attempt_number: 1,
      status: "failed",
      provider_message_id: "SIM-abc123",
      is_simulated: true,
      failure_class: "transient",
      failure_code: "SIM-TRANSIENT",
      failure_reason: "Simulated provider outage",
      is_permanent: false,
      started_at: "2026-11-14T09:00:01Z",
      next_attempt_at: null,
      terminal_at: null,
      events: [
        {
          source: "send_response",
          provider_status: "accepted",
          normalised_status: "accepted",
          applied: true,
          ignore_reason: null,
          received_at: "2026-11-14T09:00:02Z",
        },
      ],
    },
  ],
};

const aiMetrics: AiMetrics = {
  window_days: 30,
  total_requests: 55,
  failed_requests: 4,
  input_tokens: 1000,
  output_tokens: 400,
  estimated_cost_usd: null,
  features: [
    {
      feature: "rewrite",
      requests: 30,
      failures: 1,
      accepted: 20,
      average_latency_ms: 320,
      input_tokens: 600,
      output_tokens: 250,
    },
  ],
  errors: [{ outcome: "timeout", error_code: "timeout", count: 3 }],
  daily: [{ day: "2026-11-13", requests: 5 }],
};

const auditRow: AuditLogRow = {
  id: "33333333-3333-4333-8333-333333333333",
  created_at: "2026-11-14T08:00:00Z",
  category: "admin",
  action: "admin.user_restricted",
  outcome: "success",
  actor_id: "44444444-4444-4444-8444-444444444444",
  actor_role: "admin",
  target_type: "user",
  target_id: USER_ID,
  request_id: "req-1",
};

function adminRoutes(extra: Record<string, MockHandler> = {}): Record<string, MockHandler> {
  return {
    ...signedInRoutes(makeProfile({ role: "admin" })),
    [`GET ${BASE}/dashboard`]: ok(dashboard),
    [`GET ${BASE}/providers/overview`]: ok(overview),
    [`GET ${BASE}/users`]: paged([userRow()]),
    [`GET ${BASE}/users/${USER_ID}`]: ok(userDetail()),
    [`GET ${BASE}/sms/messages`]: paged([smsRow]),
    [`GET ${BASE}/sms/messages/${MESSAGE_ID}`]: ok(smsDetail),
    [`GET ${BASE}/ai/metrics`]: ok(aiMetrics),
    [`GET ${BASE}/audit-logs`]: paged([auditRow]),
    ...extra,
  };
}

describe("Administration dashboard", () => {
  it("shows real totals, keeps simulated and live SMS apart and shows no secrets", async () => {
    mockApi(adminRoutes());
    renderApp("/admin");
    expect(await screen.findByRole("heading", { name: "Administration" })).toBeInTheDocument();

    const people = await screen.findByRole("region", { name: "People and conversations" });
    expect(within(people).getByText("42")).toBeInTheDocument();
    expect(within(people).getByText("31")).toBeInTheDocument();
    expect(within(people).getByText("230")).toBeInTheDocument();

    const sms = await screen.findByRole("region", { name: "SMS" });
    expect(within(sms).getByText("SIMULATED")).toBeInTheDocument();
    expect(within(sms).getByText("LIVE")).toBeInTheDocument();
    expect(within(sms).getByText("75%")).toBeInTheDocument();
    expect(within(sms).getAllByText("No settled messages")).toHaveLength(1);

    const credits = await screen.findByRole("region", { name: "Credit activity" });
    expect(within(credits).getByText("Simulated (demo) credits")).toBeInTheDocument();

    const provider = await screen.findByRole("region", { name: "Provider" });
    expect(within(provider).getByText("Degraded")).toBeInTheDocument();
    expect(within(provider).getByText(/callbacks could not be processed/)).toBeInTheDocument();
    expect(within(provider).getByText("Philippines")).toBeInTheDocument();
    expect(within(provider).getByText("Values are never shown")).toBeInTheDocument();
  });

  it("is not available to non-administrators and requests nothing from the admin API", async () => {
    const api = mockApi({
      ...adminRoutes(),
      "GET /api/v1/users/me": ok(makeProfile({ role: "user" })),
    });
    renderApp("/admin/users");
    expect(await screen.findByText(/Only administrators/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Administration" })).not.toBeInTheDocument();
    expect(api.callsTo("GET", `${BASE}/users`)).toHaveLength(0);
  });

  it("shows a readable error with a retry when the backend refuses", async () => {
    mockApi(adminRoutes({ [`GET ${BASE}/dashboard`]: fail(500, "internal_error", "Failed") }));
    renderApp("/admin");
    expect(await screen.findByRole("button", { name: /try again|retry/i })).toBeInTheDocument();
  });

  it("only offers the admin entry in the navigation to administrators", async () => {
    mockApi({
      ...adminRoutes(),
      "GET /api/v1/users/me": ok(makeProfile({ role: "user" })),
    });
    renderApp("/");
    await screen.findByRole("navigation", { name: "Main" });
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });
});

describe("Administration users", () => {
  it("searches with the typed term and shows only masked details", async () => {
    const api = mockApi(adminRoutes());
    const user = userEvent.setup();
    renderApp("/admin/users");
    expect(await screen.findByText("m***@example.com")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Search by name, username or email"), "marites");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() =>
      expect(api.callsTo("GET", `${BASE}/users`).some((c) => c.search.includes("q=marites"))).toBe(
        true,
      ),
    );

    await user.click(await screen.findByRole("button", { name: "View Marites Santos" }));
    const detail = await screen.findByRole("region", { name: "Account details" });
    expect(within(detail).getByText(/\+63\*\*\*\*4567/)).toBeInTheDocument();
    expect(within(detail).getByText("Chikka messages sent")).toBeInTheDocument();
  });

  it("restricts an account only after confirmation, with the chosen reason", async () => {
    const api = mockApi(
      adminRoutes({
        [`POST ${BASE}/users/${USER_ID}/restrict`]: ok(userRow({ status: "suspended" })),
      }),
    );
    const user = userEvent.setup();
    renderApp("/admin/users");
    await user.click(await screen.findByRole("button", { name: "View Marites Santos" }));
    await screen.findByRole("region", { name: "Account details" });
    await user.selectOptions(screen.getByLabelText("Reason for restriction"), "spam");
    await user.click(screen.getByRole("button", { name: "Restrict account" }));
    expect(api.callsTo("POST", `${BASE}/users/${USER_ID}/restrict`)).toHaveLength(0);

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Restrict account" }));
    await waitFor(() =>
      expect(api.callsTo("POST", `${BASE}/users/${USER_ID}/restrict`)).toHaveLength(1),
    );
    expect(api.callsTo("POST", `${BASE}/users/${USER_ID}/restrict`)[0]?.body).toEqual({
      reason_code: "spam",
    });
  });

  it("offers no restriction for administrators and lifts a suspension", async () => {
    const api = mockApi(
      adminRoutes({
        [`GET ${BASE}/users`]: paged([userRow({ status: "suspended" })]),
        [`GET ${BASE}/users/${USER_ID}`]: ok(userDetail({ status: "suspended" })),
        [`POST ${BASE}/users/${USER_ID}/reinstate`]: ok(userRow()),
      }),
    );
    const user = userEvent.setup();
    renderApp("/admin/users");
    await user.click(await screen.findByRole("button", { name: "View Marites Santos" }));
    expect(screen.queryByRole("button", { name: "Restrict account" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Lift restriction" }));
    await waitFor(() =>
      expect(api.callsTo("POST", `${BASE}/users/${USER_ID}/reinstate`)).toHaveLength(1),
    );
  });

  it("explains a refused restriction", async () => {
    mockApi(
      adminRoutes({
        [`POST ${BASE}/users/${USER_ID}/restrict`]: fail(
          409,
          "cannot_restrict_administrator",
          "Administrator accounts cannot be restricted here.",
        ),
      }),
    );
    const user = userEvent.setup();
    renderApp("/admin/users");
    await user.click(await screen.findByRole("button", { name: "View Marites Santos" }));
    await screen.findByRole("region", { name: "Account details" });
    await user.click(screen.getByRole("button", { name: "Restrict account" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Restrict account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/cannot be restricted/i);
  });

  it("explains when no account matches", async () => {
    mockApi(adminRoutes({ [`GET ${BASE}/users`]: paged([]) }));
    renderApp("/admin/users");
    expect(await screen.findByText(/No accounts match/)).toBeInTheDocument();
  });
});

describe("Administration SMS, AI and audit views", () => {
  it("lists SMS with failure reasons and shows attempts and provider IDs", async () => {
    mockApi(adminRoutes());
    const user = userEvent.setup();
    renderApp("/admin/messages");
    expect(await screen.findByText("+12****0104")).toBeInTheDocument();
    expect(screen.getByText("SIMULATED")).toBeInTheDocument();
    expect(screen.getByText(/couldn't reach the SMS provider/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: `Attempts for message ${MESSAGE_ID}` }));
    const attempts = await screen.findByRole("region", { name: "Delivery attempts" });
    expect(within(attempts).getByText(/SIM-abc123/)).toBeInTheDocument();
    expect(within(attempts).getByText(/Attempt 1: failed/)).toBeInTheDocument();
    expect(within(attempts).getByText(/SIM-TRANSIENT/)).toBeInTheDocument();
  });

  it("switches to inbound messages", async () => {
    const api = mockApi(adminRoutes());
    const user = userEvent.setup();
    renderApp("/admin/messages");
    await screen.findByText("+12****0104");
    await user.selectOptions(screen.getByLabelText("Direction"), "inbound");
    await waitFor(() =>
      expect(
        api
          .callsTo("GET", `${BASE}/sms/messages`)
          .some((c) => c.search.includes("direction=inbound")),
      ).toBe(true),
    );
  });

  it("shows AI usage and says cost is unavailable instead of inventing it", async () => {
    mockApi(adminRoutes());
    renderApp("/admin/ai");
    expect(await screen.findByText("rewrite")).toBeInTheDocument();
    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(screen.getByText(/timeout \(timeout\): 3/)).toBeInTheDocument();
    expect(screen.getByText(/never displayed/)).toBeInTheDocument();
  });

  it("shows the audit log with actor, action, resource and outcome", async () => {
    const api = mockApi(adminRoutes());
    const user = userEvent.setup();
    renderApp("/admin/audit");
    expect(await screen.findByText("admin.user_restricted")).toBeInTheDocument();
    expect(screen.getByText("Succeeded", { selector: "td" })).toBeInTheDocument();
    expect(screen.getByText(/^admin 44444444$/)).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Outcome"), "denied");
    await waitFor(() =>
      expect(
        api.callsTo("GET", `${BASE}/audit-logs`).some((c) => c.search.includes("outcome=denied")),
      ).toBe(true),
    );
  });
});
