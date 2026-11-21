import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { CreditBadge } from "@/features/credits/components/CreditBadge";
import { CreditsOverview } from "@/features/credits/components/CreditsOverview";
import { LowCreditWarning } from "@/features/credits/components/LowCreditWarning";
import type { Balance, CreditTransaction } from "@/features/credits/types";
import { SmsQuotePanel } from "@/features/sms/components/SmsQuotePanel";
import type { Quote } from "@/features/sms/types";
import { fail, mockApi, ok, type MockReply } from "@/test/api-mock";

const BALANCE = "/api/v1/credits";
const HISTORY = "/api/v1/credits/transactions";

function balance(available = 5000, overrides: Partial<Balance> = {}): Balance {
  return {
    ledgers: [
      {
        ledger: "demo",
        balance_units: available,
        reserved_units: 0,
        available_units: available,
        available_credits: available / 100,
        charges_apply: true,
      },
      {
        ledger: "live",
        balance_units: 0,
        reserved_units: 0,
        available_units: 0,
        available_credits: 0,
        charges_apply: false,
      },
    ],
    active_ledger: "demo",
    is_simulated: true,
    low_balance_threshold_units: 500,
    is_low: available <= 500,
    notice: "These are simulated credits for demonstration. They are not money.",
    ...overrides,
  };
}

function entry(overrides: Partial<CreditTransaction> = {}): CreditTransaction {
  return {
    id: "tx-1",
    ledger: "demo",
    entry_type: "deduction",
    description: "SMS sent",
    balance_delta: -100,
    reserved_delta: -100,
    credits_delta: -1,
    balance_after: 4900,
    message_id: "m-1",
    provider: "mock",
    country_code: "PH",
    segment_count: 1,
    reason: null,
    created_at: "2026-11-14T08:00:00Z",
    ...overrides,
  };
}

function page(items: CreditTransaction[], overrides = {}): MockReply {
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

function wrap(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("credit overview", () => {
  it("shows the balance, the not-money notice and the history", async () => {
    mockApi({
      [`GET ${BALANCE}`]: ok(balance()),
      [`GET ${HISTORY}`]: page([
        entry(),
        entry({
          id: "tx-0",
          entry_type: "grant",
          description: "Starting demo credits",
          balance_delta: 5000,
          reserved_delta: 0,
          credits_delta: 50,
          balance_after: 5000,
          message_id: null,
          country_code: null,
          segment_count: null,
          created_at: "2026-11-13T08:00:00Z",
        }),
      ]),
    });
    wrap(<CreditsOverview />);

    expect(await screen.findByText("50.00")).toBeInTheDocument();
    expect(screen.getByText(/They are not money/)).toBeInTheDocument();
    const list = await screen.findByRole("list", { name: "Credit transactions" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]!).getByText("SMS sent")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("-1.00")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("Balance 49.00")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("+50.00")).toBeInTheDocument();
  });

  it("shows holds as held, not as spent", async () => {
    mockApi({
      [`GET ${BALANCE}`]: ok(balance(4900)),
      [`GET ${HISTORY}`]: page([
        entry({
          id: "tx-h",
          entry_type: "reservation",
          description: "Held for an SMS being sent",
          balance_delta: 0,
          reserved_delta: 100,
          credits_delta: 0,
        }),
      ]),
    });
    wrap(<CreditsOverview />);

    const row = (await screen.findAllByRole("listitem"))[0]!;
    expect(within(row).getByText("Held for an SMS being sent")).toBeInTheDocument();
    expect(row).toHaveTextContent("1.00 held");
  });

  it("explains reserved credits", async () => {
    const data = balance(4900);
    data.ledgers[0]!.reserved_units = 100;
    mockApi({ [`GET ${BALANCE}`]: ok(data), [`GET ${HISTORY}`]: page([]) });
    wrap(<CreditsOverview />);

    expect(
      await screen.findByText(/1\.00 credits are held for messages being sent/),
    ).toBeInTheDocument();
  });

  it("pages through the history", async () => {
    const api = mockApi({
      [`GET ${BALANCE}`]: ok(balance()),
      [`GET ${HISTORY}`]: (request) =>
        request.search.includes("page=2")
          ? page([entry({ id: "old", description: "Refund: the SMS failed" })], {
              page: 2,
              has_prev: true,
            })
          : page([entry()], { has_next: true, total: 2 }),
    });
    const user = userEvent.setup();
    wrap(<CreditsOverview />);

    await screen.findByText("SMS sent");
    await user.click(screen.getByRole("button", { name: "Older" }));

    expect(await screen.findByText("Refund: the SMS failed")).toBeInTheDocument();
    expect(api.callsTo("GET", HISTORY).map((call) => call.search)).toEqual(
      expect.arrayContaining([expect.stringContaining("page=2")]),
    );
    expect(screen.getByRole("button", { name: "Newer" })).toBeEnabled();
  });

  it("handles an empty history", async () => {
    mockApi({ [`GET ${BALANCE}`]: ok(balance()), [`GET ${HISTORY}`]: page([]) });
    wrap(<CreditsOverview />);

    expect(await screen.findByText("No credit activity yet")).toBeInTheDocument();
  });

  it("offers a retry when the history cannot be loaded", async () => {
    let calls = 0;
    mockApi({
      [`GET ${BALANCE}`]: ok(balance()),
      [`GET ${HISTORY}`]: () => {
        calls += 1;
        return calls === 1 ? fail(503, "service_unavailable", "Try again soon.") : page([entry()]);
      },
    });
    const user = userEvent.setup();
    wrap(<CreditsOverview />);

    await user.click(await screen.findByRole("button", { name: "Try again" }));

    expect(await screen.findByText("SMS sent")).toBeInTheDocument();
  });

  it("warns when credits are low", async () => {
    mockApi({ [`GET ${BALANCE}`]: ok(balance(300)), [`GET ${HISTORY}`]: page([]) });
    wrap(<CreditsOverview />);

    expect(
      await screen.findByText(/Your demo credits are running low: 3\.00 left/),
    ).toBeInTheDocument();
  });
});

describe("credit badge and low-credit warning", () => {
  it("shows the active ledger's balance as a link to the history", async () => {
    mockApi({ [`GET ${BALANCE}`]: ok(balance()) });
    wrap(<CreditBadge />);

    const link = await screen.findByRole("link", { name: /50\.00 demo credits/ });
    expect(link).toHaveAttribute("href", "/credits");
  });

  it("marks a low balance", async () => {
    mockApi({ [`GET ${BALANCE}`]: ok(balance(400)) });
    wrap(<CreditBadge />);

    expect(await screen.findByRole("link", { name: /low balance/ })).toBeInTheDocument();
  });

  it("stays out of the way when the balance cannot be loaded", async () => {
    const api = mockApi({ [`GET ${BALANCE}`]: fail(500, "internal_error") });
    wrap(<CreditBadge />);

    await waitFor(() => expect(api.callsTo("GET", BALANCE)).toHaveLength(1));
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("says plainly when there are no credits left", async () => {
    mockApi({ [`GET ${BALANCE}`]: ok(balance(0)) });
    wrap(<LowCreditWarning />);

    expect(
      await screen.findByText(/out of demo credits, so new SMS cannot be sent/),
    ).toBeInTheDocument();
  });

  it("is silent when the balance is fine", async () => {
    const api = mockApi({ [`GET ${BALANCE}`]: ok(balance()) });
    wrap(<LowCreditWarning />);

    await waitFor(() => expect(api.callsTo("GET", BALANCE)).toHaveLength(1));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("SMS cost preview", () => {
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
      warnings: [],
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
      balance: {
        ledger: "demo",
        is_simulated: true,
        available_units: 5000,
        available_credits: 50,
        sufficient: true,
        charges_apply: true,
        is_low: false,
      },
      consent: { required: false, granted: true, notice_version: "2026-11-01" },
      recipient_opted_out: false,
      blockers: [],
      can_send: true,
      ...overrides,
    };
  }

  function panel(q: Quote) {
    wrap(
      <SmsQuotePanel
        body="Hello"
        quote={q}
        loading={false}
        failed={false}
        consentPending={false}
        onConsentChange={() => undefined}
      />,
    );
  }

  it("shows the cost, the balance and what is left afterwards", () => {
    panel(quote());

    expect(screen.getByText(/Estimated 1\.00 demo credits \(demo rate\)/)).toBeInTheDocument();
    expect(screen.getByText(/You have 50\.00, 49\.00 after this message/)).toBeInTheDocument();
    expect(screen.getByText(/refunded if it fails/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Credit history" })).toHaveAttribute(
      "href",
      "/credits",
    );
    expect(screen.queryByText(/running low/)).not.toBeInTheDocument();
  });

  it("warns when the balance is low but still enough", () => {
    panel(quote({ balance: { ...quote().balance, available_credits: 4, is_low: true } }));

    expect(screen.getByText("Your demo credits are running low.")).toBeInTheDocument();
  });

  it("shows the insufficient-credits blocker and no after-balance", () => {
    panel(
      quote({
        balance: {
          ...quote().balance,
          available_units: 50,
          available_credits: 0.5,
          sufficient: false,
          is_low: true,
        },
        blockers: [
          {
            code: "insufficient_credits",
            message: "This message costs 1.00 demo credits and you have 0.50.",
          },
        ],
        can_send: false,
      }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "costs 1.00 demo credits and you have 0.50",
    );
    expect(screen.queryByText(/after this message/)).not.toBeInTheDocument();
    expect(screen.queryByText("Your demo credits are running low.")).not.toBeInTheDocument();
  });

  it("does not talk about demo credits for a live route", () => {
    panel(
      quote({
        mode: "live",
        is_simulated: false,
        balance: { ...quote().balance, is_simulated: false, charges_apply: false, ledger: "live" },
      }),
    );

    expect(screen.queryByText(/Demo credits are charged/)).not.toBeInTheDocument();
    expect(screen.getByText(/Estimated 1\.00 credits/)).toBeInTheDocument();
  });
});
