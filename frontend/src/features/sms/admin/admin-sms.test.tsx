import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { AdminProvider, Monitoring } from "@/features/sms/admin/api";
import { fail, makeProfile, mockApi, ok, signedInRoutes, type MockHandler } from "@/test/api-mock";
import { renderApp } from "@/test/render-app";

const BASE = "/api/v1/admin/sms";

function provider(overrides: Partial<AdminProvider> = {}): AdminProvider {
  return {
    id: "p-mock",
    provider: "mock",
    display_name: "Simulation (MockSmsProvider)",
    mode: "simulation",
    is_active: true,
    is_running: true,
    credentials_configured: true,
    sender_registration_status: "not_required",
    webhook_path: "/api/v1/webhooks/mock",
    max_retry_attempts: 3,
    retry_base_seconds: 5,
    retry_cap_seconds: 300,
    retry_multiplier: 2,
    sender_numbers: ["+12****0190"],
    live_confirmed_at: null,
    live_confirmed_environment: null,
    ...overrides,
  };
}

function monitoring(overrides: Partial<Monitoring> = {}): Monitoring {
  return {
    mode: "simulation",
    provider: "mock",
    outbound_paused: false,
    dispatch_paused_by_configuration_error: false,
    queue_depth: 0,
    last_24h: [],
    delivery_rate: 0.5,
    failure_rate: 0.5,
    unrouted_inbound: 1,
    webhook_processing_failures: 0,
    webhook_orphaned: 0,
    webhook_signature_rejections: 2,
    opt_outs: 0,
    recent_failures: [
      {
        message_id: "m-1",
        created_at: "2026-11-12T10:00:00Z",
        status: "failed",
        is_simulated: true,
        attempts: 1,
        failure_class: "permanent",
        failure_code: "SIM-FAILED",
        reason: "Simulated failure: the provider reported the message as failed.",
        masked_recipient: "+12****0101",
      },
    ],
    ...overrides,
  };
}

function adminRoutes(extra: Record<string, MockHandler> = {}): Record<string, MockHandler> {
  return {
    ...signedInRoutes(makeProfile({ role: "admin" })),
    [`GET ${BASE}/monitoring`]: ok(monitoring()),
    [`GET ${BASE}/providers`]: ok([
      provider(),
      provider({
        id: "p-twilio",
        provider: "twilio",
        display_name: "Twilio (live)",
        mode: "live",
        is_active: false,
        is_running: false,
        credentials_configured: false,
        sender_numbers: [],
      }),
    ]),
    [`GET ${BASE}/capabilities`]: ok([
      {
        country_code: "PH",
        country_name: "Philippines",
        dial_code: 63,
        version: 1,
        outbound_support: "requires_verification",
        inbound_support: "requires_verification",
        registered_sender_required: true,
        registered_sender_status: "not_registered",
        price_units_per_segment: null,
        supported_number_types: ["mobile"],
        consent_required: true,
        content_restrictions: null,
        verified: false,
      },
    ]),
    [`GET ${BASE}/inbound/unrouted`]: {
      status: 200,
      body: {
        data: [
          {
            id: "u-1",
            received_at: "2026-11-12T10:00:00Z",
            is_simulated: false,
            masked_sender: "+12****0177",
            masked_platform_number: "+12****0190",
            retained_until: "2027-02-10T10:00:00Z",
          },
        ],
        pagination: { total: 1, page: 1, page_size: 30, has_next: false, has_prev: false },
        request_id: "r",
      },
    },
    ...extra,
  };
}

describe("SMS administration", () => {
  it("shows providers without any secret, capabilities, unrouted replies and failures", async () => {
    mockApi(adminRoutes());
    renderApp("/admin/sms");
    expect(await screen.findByRole("heading", { name: "SMS administration" })).toBeInTheDocument();
    const providers = await screen.findByRole("region", { name: "Providers" });
    expect(within(providers).getAllByText("Credentials:", { exact: false })).toHaveLength(2);
    expect(within(providers).getByText("not configured")).toBeInTheDocument();
    // No input can reveal or edit a credential.
    expect(
      within(providers).queryByLabelText(/token|secret|password|auth/i),
    ).not.toBeInTheDocument();
    const capabilities = await screen.findByRole("region", { name: "Country capabilities" });
    expect(within(capabilities).getByText("Philippines")).toBeInTheDocument();
    expect(within(capabilities).getByText("not_registered")).toBeInTheDocument();
    const unrouted = await screen.findByRole("region", {
      name: "Replies that matched no conversation",
    });
    expect(within(unrouted).getByText(/\+12\*\*\*\*0177/)).toBeInTheDocument();
    expect(await screen.findByText("+12****0101")).toBeInTheDocument();
    expect(screen.getByText(/Simulated failure/)).toBeInTheDocument();
  });

  it("is not available to non-administrators", async () => {
    mockApi({ ...adminRoutes(), "GET /api/v1/users/me": ok(makeProfile({ role: "user" })) });
    renderApp("/admin/sms");
    expect(await screen.findByText(/Only administrators/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "SMS administration" })).not.toBeInTheDocument();
  });

  it("pauses all sending and validates retry settings before saving", async () => {
    const api = mockApi(adminRoutes({ [`PUT ${BASE}/outbound-paused`]: ok({ paused: true }) }));
    const user = userEvent.setup();
    renderApp("/admin/sms");
    await user.click(await screen.findByRole("button", { name: "Pause all sending" }));
    await waitFor(() => expect(api.callsTo("PUT", `${BASE}/outbound-paused`)).toHaveLength(1));
    expect(api.callsTo("PUT", `${BASE}/outbound-paused`)[0]?.body).toEqual({ paused: true });

    const providers = await screen.findByRole("region", { name: "Providers" });
    const forms = within(providers).getAllByLabelText("Longest wait (seconds)");
    await user.clear(forms[0] as HTMLElement);
    await user.type(forms[0] as HTMLElement, "2");
    await user.click(
      within(providers).getAllByRole("button", { name: "Save retry settings" })[0] as HTMLElement,
    );
    expect(await screen.findByText(/at least the first wait/)).toBeInTheDocument();
    expect(api.callsTo("PATCH", `${BASE}/providers/p-mock`)).toHaveLength(0);
  });

  it("requires typing the environment before activating live SMS, and shows the server's refusal", async () => {
    const api = mockApi(
      adminRoutes({
        [`GET ${BASE}/providers`]: ok([
          provider({ is_active: false, is_running: false }),
          provider({
            id: "p-twilio",
            provider: "twilio",
            display_name: "Twilio (live)",
            mode: "live",
            is_active: false,
            is_running: true,
            credentials_configured: true,
          }),
        ]),
        [`POST ${BASE}/providers/p-twilio/activate`]: fail(
          422,
          "environment_mismatch",
          "Type the environment name (test) to confirm live SMS.",
        ),
      }),
    );
    const user = userEvent.setup();
    renderApp("/admin/sms");
    const button = await screen.findByRole("button", { name: "Confirm and activate live SMS" });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/Type this environment's name/), "production");
    await user.click(button);
    expect(await screen.findByText(/Type the environment name \(test\)/)).toBeInTheDocument();
    expect(api.callsTo("POST", `${BASE}/providers/p-twilio/activate`)[0]?.body).toEqual({
      confirm_environment: "production",
    });
  });

  it("sends a simulated reply through the API only in simulation mode", async () => {
    const api = mockApi(
      adminRoutes({
        [`POST ${BASE}/simulate/inbound`]: ok({ duplicate: false, routing_result: "routed" }),
      }),
    );
    const user = userEvent.setup();
    renderApp("/admin/sms");
    await user.type(await screen.findByLabelText("From (the phone replying)"), "+12025550142");
    await user.type(screen.getByLabelText("To (our sender number)"), "+12025550190");
    await user.type(screen.getByLabelText("Reply text"), "Okay po");
    await user.click(screen.getByRole("button", { name: "Simulate reply" }));
    expect(await screen.findByText(/Reply processed: routed/)).toBeInTheDocument();
    expect(api.callsTo("POST", `${BASE}/simulate/inbound`)[0]?.body).toEqual({
      from_phone: "+12025550142",
      to_number: "+12025550190",
      body: "Okay po",
    });
  });

  it("hides the reply simulator in live mode", async () => {
    mockApi(
      adminRoutes({
        [`GET ${BASE}/monitoring`]: ok(monitoring({ mode: "live", provider: "twilio" })),
      }),
    );
    renderApp("/admin/sms");
    await screen.findByRole("region", { name: "Providers" });
    await screen.findByText(/Running: twilio \(live\)/);
    expect(screen.queryByRole("region", { name: "Simulate a reply" })).not.toBeInTheDocument();
  });
});
