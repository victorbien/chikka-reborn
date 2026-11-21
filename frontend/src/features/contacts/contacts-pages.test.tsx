import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type {
  BlockItem,
  ContactDetail,
  ContactGroup,
  ContactRequestItem,
  ContactSummary,
  Pagination,
} from "@/features/contacts/types";
import { fail, mockApi, ok, signedInRoutes, type MockHandler } from "@/test/api-mock";
import { renderApp } from "@/test/render-app";

const BASE = "/api/v1/contacts";

function contact(overrides: Partial<ContactSummary> = {}): ContactSummary {
  return {
    id: "c-1",
    contact_type: "chikka",
    user_id: "u-1",
    username: "juan_dc",
    display_name: "Juan dela Cruz",
    nickname: null,
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

function detail(overrides: Partial<ContactDetail> = {}): ContactDetail {
  return {
    ...contact(),
    bio: "Hello from Cebu",
    country_code: "PH",
    added_at: "2026-11-01T00:00:00Z",
    ...overrides,
  };
}

function pagination(total: number): Pagination {
  return { total, page: 1, page_size: 50, has_next: false, has_prev: false };
}

function paged<T>(items: T[]) {
  return {
    status: 200,
    body: { data: items, pagination: pagination(items.length), request_id: "req-test" },
  };
}

function request(overrides: Partial<ContactRequestItem> = {}): ContactRequestItem {
  return {
    id: "r-1",
    direction: "incoming",
    person: { user_id: "u-9", username: "ana_r", display_name: "Ana Reyes", avatar_url: null },
    note: "Hi, it's Ana",
    created_at: "2026-11-10T00:00:00Z",
    expires_at: "2026-12-10T00:00:00Z",
    ...overrides,
  };
}

const GROUP: ContactGroup = {
  id: "g-1",
  name: "Family",
  color: null,
  position: 0,
  member_count: 1,
};

function contactRoutes(extra: Record<string, MockHandler> = {}): Record<string, MockHandler> {
  return {
    ...signedInRoutes(),
    [`GET ${BASE}`]: paged([contact()]),
    [`GET ${BASE}/groups`]: ok([]),
    [`GET ${BASE}/requests`]: paged<ContactRequestItem>([]),
    [`GET ${BASE}/blocks`]: ok([]),
    [`GET ${BASE}/recent`]: ok([]),
    [`GET ${BASE}/recent-conversations`]: ok([]),
    ...extra,
  };
}

describe("buddy list", () => {
  it("shows presence with a text label, the status message and the SMS badge", async () => {
    mockApi(
      contactRoutes({
        [`GET ${BASE}`]: paged([
          contact(),
          contact({
            id: "c-2",
            user_id: "u-2",
            display_name: "Maria Santos",
            presence: "unknown",
            status_message: null,
          }),
          contact({
            id: "c-3",
            contact_type: "sms",
            user_id: null,
            username: null,
            display_name: "Nanay",
            masked_phone: "+63****4567",
            presence: "unknown",
            status_message: null,
          }),
        ]),
      }),
    );
    renderApp("/contacts");
    const list = await screen.findByRole("list", { name: "Contacts" });
    expect(within(list).getByText("Juan dela Cruz")).toBeInTheDocument();
    expect(within(list).getByText("At work")).toBeInTheDocument();
    // Status is never colour alone.
    expect(within(list).getByRole("img", { name: "Online" })).toBeInTheDocument();
    expect(within(list).getByRole("img", { name: "Presence hidden" })).toBeInTheDocument();
    expect(within(list).getByText("SMS only")).toBeInTheDocument();
    expect(within(list).getByText("+63****4567")).toBeInTheDocument();
  });

  it("explains an empty list and offers the next step", async () => {
    mockApi(contactRoutes({ [`GET ${BASE}`]: paged([]) }));
    renderApp("/contacts");
    expect(await screen.findByText("No contacts yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add contact" })).toBeInTheDocument();
  });

  it("shows a readable error with a retry", async () => {
    let attempts = 0;
    mockApi(
      contactRoutes({
        [`GET ${BASE}`]: () => {
          attempts += 1;
          return attempts === 1
            ? fail(500, "internal_error", "Server problem.")
            : paged([contact()]);
        },
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Request ID: req-fail")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Juan dela Cruz")).toBeInTheDocument();
  });

  it("filters by online, offline and favourites through the API", async () => {
    const api = mockApi(contactRoutes());
    const user = userEvent.setup();
    renderApp("/contacts");
    await screen.findByText("Juan dela Cruz");
    for (const [label, filter] of [
      ["Online", "online"],
      ["Offline", "offline"],
      ["Favourites", "favourites"],
    ] as const) {
      await user.click(screen.getByRole("button", { name: label }));
      await waitFor(() =>
        expect(api.callsTo("GET", BASE).some((c) => c.search.includes(`filter=${filter}`))).toBe(
          true,
        ),
      );
    }
    expect(screen.getByRole("button", { name: "Favourites" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("filters by group", async () => {
    const api = mockApi(contactRoutes({ [`GET ${BASE}/groups`]: ok([GROUP]) }));
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.selectOptions(await screen.findByLabelText("Group"), "g-1");
    await waitFor(() =>
      expect(
        api
          .callsTo("GET", BASE)
          .some((c) => c.search.includes("filter=group") && c.search.includes("group_id=g-1")),
      ).toBe(true),
    );
  });

  it("toggles a favourite", async () => {
    const api = mockApi(
      contactRoutes({ [`PATCH ${BASE}/c-1`]: ok(detail({ is_favourite: true })) }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Favourite Juan dela Cruz" }));
    await waitFor(() => expect(api.callsTo("PATCH", `${BASE}/c-1`)).toHaveLength(1));
    expect(api.callsTo("PATCH", `${BASE}/c-1`)[0]?.body).toEqual({ is_favourite: true });
  });
});

describe("finding people", () => {
  const person = {
    user_id: "u-5",
    username: "pedro_p",
    display_name: "Pedro Penduko",
    avatar_url: null,
    relationship: "none",
    contact_id: null,
    request_id: null,
  };

  it("sends nothing for one character, then searches after the pause", async () => {
    const api = mockApi(
      contactRoutes({ [`GET ${BASE}/search`]: ok({ contacts: [], people: [person] }) }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    const box = await screen.findByLabelText("Search contacts");
    await user.type(box, "p");
    expect(screen.getByText("Type at least 2 characters.")).toBeInTheDocument();
    expect(api.callsTo("GET", `${BASE}/search`)).toHaveLength(0);
    await user.type(box, "edro_p");
    expect(await screen.findByText("Pedro Penduko")).toBeInTheDocument();
    // Typing fast produced one request for the final text, not one per key.
    const searches = api.callsTo("GET", `${BASE}/search`);
    expect(searches).toHaveLength(1);
    expect(searches[0]?.search).toBe("?q=pedro_p");
  });

  it("sends a request from a search result and then shows it as sent", async () => {
    const api = mockApi(
      contactRoutes({
        [`GET ${BASE}/search`]: ok({ contacts: [], people: [person] }),
        [`POST ${BASE}/requests`]: ok({ status: "sent" }),
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.type(await screen.findByLabelText("Search contacts"), "pedro_p");
    await user.click(await screen.findByRole("button", { name: "Add Pedro Penduko" }));
    expect(await screen.findByText("Request sent")).toBeInTheDocument();
    expect(api.callsTo("POST", `${BASE}/requests`)[0]?.body).toEqual({
      user_id: "u-5",
      note: null,
    });
  });

  it("explains an empty search without hinting at who is registered", async () => {
    mockApi(contactRoutes({ [`GET ${BASE}/search`]: ok({ contacts: [], people: [] }) }));
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.type(await screen.findByLabelText("Search contacts"), "someone@example.com");
    expect(await screen.findByText(/No matches\./)).toBeInTheDocument();
    expect(screen.queryByText(/not registered|doesn't exist|no account/i)).not.toBeInTheDocument();
  });

  it("shows the rate limit message from the server", async () => {
    mockApi(
      contactRoutes({
        [`GET ${BASE}/search`]: fail(429, "rate_limited", "Too many searches. Please wait."),
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.type(await screen.findByLabelText("Search contacts"), "juan");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Too many searches|too many/i);
  });

  it("adds a contact from the dialog with a validated note", async () => {
    const api = mockApi(
      contactRoutes({
        [`GET ${BASE}/search`]: ok({ contacts: [], people: [person] }),
        [`POST ${BASE}/requests`]: ok({ status: "sent" }),
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Add contact" }));
    const dialog = await screen.findByRole("dialog", { name: "Add a contact" });
    await user.type(within(dialog).getByLabelText("Note (optional)"), "x".repeat(141));
    expect(await within(dialog).findByText("Use at most 140 characters.")).toBeInTheDocument();
    await user.clear(within(dialog).getByLabelText("Note (optional)"));
    await user.type(within(dialog).getByLabelText("Note (optional)"), "Kumusta!");
    await user.type(within(dialog).getByLabelText("Username, email or mobile number"), "pedro_p");
    await user.click(await within(dialog).findByRole("button", { name: "Add Pedro Penduko" }));
    await waitFor(() => expect(api.callsTo("POST", `${BASE}/requests`)).toHaveLength(1));
    expect(api.callsTo("POST", `${BASE}/requests`)[0]?.body).toEqual({
      user_id: "u-5",
      note: "Kumusta!",
    });
  });
});

describe("contact requests", () => {
  it("accepts a request", async () => {
    const api = mockApi(
      contactRoutes({
        [`GET ${BASE}/requests`]: paged([request()]),
        [`POST ${BASE}/requests/r-1/accept`]: ok(detail()),
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    expect(await screen.findByRole("button", { name: "Requests (1)" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Requests (1)" }));
    expect(await screen.findByText("“Hi, it's Ana”")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Accept request from Ana Reyes" }));
    await waitFor(() => expect(api.callsTo("POST", `${BASE}/requests/r-1/accept`)).toHaveLength(1));
  });

  it("rejects, and can reject and block", async () => {
    const api = mockApi(
      contactRoutes({
        [`GET ${BASE}/requests`]: paged([request()]),
        [`POST ${BASE}/requests/r-1/reject`]: { status: 204 },
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Requests (1)" }));
    await user.click(await screen.findByRole("button", { name: "Reject request from Ana Reyes" }));
    await user.click(screen.getByRole("button", { name: "Reject and block Ana Reyes" }));
    await waitFor(() => expect(api.callsTo("POST", `${BASE}/requests/r-1/reject`)).toHaveLength(2));
    expect(api.callsTo("POST", `${BASE}/requests/r-1/reject`).map((c) => c.body)).toEqual([
      { block: false },
      { block: true },
    ]);
  });

  it("cancels a sent request and shows a friendly message if it already resolved", async () => {
    mockApi(
      contactRoutes({
        [`GET ${BASE}/requests`]: (req) =>
          paged([
            request({
              id: "r-2",
              direction: req.search.includes("outgoing") ? "outgoing" : "incoming",
            }),
          ]),
        [`DELETE ${BASE}/requests/r-2`]: fail(
          409,
          "request_unavailable",
          "This request is no longer available.",
        ),
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: /^Requests/ }));
    await user.click(screen.getByRole("button", { name: "Sent" }));
    await user.click(await screen.findByRole("button", { name: "Cancel request to Ana Reyes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This request is no longer available.",
    );
  });

  it("shows an empty state", async () => {
    mockApi(contactRoutes());
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Requests" }));
    expect(await screen.findByText("No requests waiting")).toBeInTheDocument();
  });
});

describe("contact profile drawer", () => {
  async function openDrawer(extra: Record<string, MockHandler> = {}) {
    const api = mockApi(
      contactRoutes({
        [`GET ${BASE}/groups`]: ok([GROUP]),
        [`GET ${BASE}/c-1`]: ok(detail()),
        ...extra,
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: /Juan dela Cruz.*At work/ }));
    const drawer = await screen.findByRole("dialog", { name: "Juan dela Cruz" });
    return { api, user, drawer };
  }

  it("shows the profile", async () => {
    const { drawer } = await openDrawer();
    expect(await within(drawer).findByText("Hello from Cebu")).toBeInTheDocument();
    expect(within(drawer).getByText("@juan_dc")).toBeInTheDocument();
    expect(within(drawer).getByText("At work")).toBeInTheDocument();
  });

  it("assigns the contact to a group", async () => {
    const { api, user, drawer } = await openDrawer({
      [`POST ${BASE}/groups/g-1/members`]: ok(GROUP),
    });
    await user.click(await within(drawer).findByRole("checkbox", { name: "Family" }));
    await waitFor(() => expect(api.callsTo("POST", `${BASE}/groups/g-1/members`)).toHaveLength(1));
    expect(api.callsTo("POST", `${BASE}/groups/g-1/members`)[0]?.body).toEqual({
      contact_ids: ["c-1"],
    });
  });

  it("asks before blocking, explains the effect, then blocks", async () => {
    const { api, user, drawer } = await openDrawer({
      [`POST ${BASE}/blocks`]: {
        status: 201,
        body: { data: { user_id: "u-1" }, request_id: "r" },
      },
    });
    await user.click(await within(drawer).findByRole("button", { name: "Block" }));
    const confirm = await screen.findByRole("dialog", { name: "Block Juan dela Cruz?" });
    expect(within(confirm).getByText(/They are not told they were blocked/)).toBeInTheDocument();
    expect(api.callsTo("POST", `${BASE}/blocks`)).toHaveLength(0);
    await user.click(within(confirm).getByRole("button", { name: "Block" }));
    await waitFor(() => expect(api.callsTo("POST", `${BASE}/blocks`)).toHaveLength(1));
    expect(api.callsTo("POST", `${BASE}/blocks`)[0]?.body).toEqual({ user_id: "u-1" });
  });

  it("does not block when the confirmation is cancelled", async () => {
    const { api, user, drawer } = await openDrawer();
    await user.click(await within(drawer).findByRole("button", { name: "Block" }));
    const confirm = await screen.findByRole("dialog", { name: "Block Juan dela Cruz?" });
    await user.click(within(confirm).getByRole("button", { name: "Cancel" }));
    expect(api.callsTo("POST", `${BASE}/blocks`)).toHaveLength(0);
  });

  it("removes a contact after confirmation", async () => {
    const { api, user, drawer } = await openDrawer({ [`DELETE ${BASE}/c-1`]: { status: 204 } });
    await user.click(await within(drawer).findByRole("button", { name: "Remove contact" }));
    const confirm = await screen.findByRole("dialog", { name: "Remove Juan dela Cruz?" });
    await user.click(within(confirm).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(api.callsTo("DELETE", `${BASE}/c-1`)).toHaveLength(1));
  });

  it("saves a nickname", async () => {
    const { api, user, drawer } = await openDrawer({
      [`PATCH ${BASE}/c-1`]: ok(detail({ nickname: "JD" })),
    });
    await user.type(await within(drawer).findByLabelText("Nickname"), "JD");
    await user.click(within(drawer).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.callsTo("PATCH", `${BASE}/c-1`)).toHaveLength(1));
    expect(api.callsTo("PATCH", `${BASE}/c-1`)[0]?.body).toEqual({ nickname: "JD" });
  });
});

describe("groups", () => {
  it("creates a group and shows a server error for a duplicate name", async () => {
    let attempts = 0;
    const api = mockApi(
      contactRoutes({
        [`POST ${BASE}/groups`]: () => {
          attempts += 1;
          return attempts === 1
            ? { status: 201, body: { data: GROUP, request_id: "r" } }
            : fail(409, "group_name_taken", "You already have a group with that name.");
        },
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Manage groups" }));
    const dialog = await screen.findByRole("dialog", { name: "Contact groups" });
    await user.type(within(dialog).getByLabelText("New group name"), "Family");
    await user.click(within(dialog).getByRole("button", { name: "Create group" }));
    await waitFor(() => expect(api.callsTo("POST", `${BASE}/groups`)).toHaveLength(1));
    await user.type(within(dialog).getByLabelText("New group name"), "Family");
    await user.click(within(dialog).getByRole("button", { name: "Create group" }));
    expect(
      await within(dialog).findByText("You already have a group with that name."),
    ).toBeInTheDocument();
  });

  it("validates the name before sending", async () => {
    const api = mockApi(contactRoutes());
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Manage groups" }));
    const dialog = await screen.findByRole("dialog", { name: "Contact groups" });
    await user.click(within(dialog).getByRole("button", { name: "Create group" }));
    expect(await within(dialog).findByText("Enter a name.")).toBeInTheDocument();
    expect(api.callsTo("POST", `${BASE}/groups`)).toHaveLength(0);
  });

  it("deletes a group only after confirming that contacts are kept", async () => {
    const api = mockApi(
      contactRoutes({
        [`GET ${BASE}/groups`]: ok([GROUP]),
        [`DELETE ${BASE}/groups/g-1`]: { status: 204 },
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Manage groups" }));
    const dialog = await screen.findByRole("dialog", { name: "Contact groups" });
    await user.click(await within(dialog).findByRole("button", { name: "Delete group Family" }));
    const confirm = await screen.findByRole("dialog", { name: /Delete the group/ });
    expect(within(confirm).getByText(/contacts in this group are kept/i)).toBeInTheDocument();
    await user.click(within(confirm).getByRole("button", { name: "Delete group" }));
    await waitFor(() => expect(api.callsTo("DELETE", `${BASE}/groups/g-1`)).toHaveLength(1));
  });
});

describe("blocked, recent and privacy", () => {
  it("lists blocked people and unblocks after confirmation", async () => {
    const blocked: BlockItem = {
      user_id: "u-7",
      person: { user_id: "u-7", username: "spam_s", display_name: "Spammer", avatar_url: null },
      blocked_at: "2026-11-10T00:00:00Z",
    };
    const api = mockApi(
      contactRoutes({
        [`GET ${BASE}/blocks`]: ok([blocked]),
        [`DELETE ${BASE}/blocks/u-7`]: { status: 204 },
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Blocked" }));
    await user.click(await screen.findByRole("button", { name: "Unblock Spammer" }));
    const confirm = await screen.findByRole("dialog", { name: "Unblock Spammer?" });
    await user.click(within(confirm).getByRole("button", { name: "Unblock" }));
    await waitFor(() => expect(api.callsTo("DELETE", `${BASE}/blocks/u-7`)).toHaveLength(1));
  });

  it("shows an empty blocked list", async () => {
    mockApi(contactRoutes());
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Blocked" }));
    expect(await screen.findByText("Nobody is blocked")).toBeInTheDocument();
  });

  it("shows recent contacts and conversations, and clears the recent list", async () => {
    const api = mockApi(
      contactRoutes({
        [`GET ${BASE}/recent`]: ok([
          { contact: contact(), conversation_id: "k-1", last_message_at: "2026-11-11T00:00:00Z" },
        ]),
        [`GET ${BASE}/recent-conversations`]: ok([
          {
            conversation_id: "k-2",
            conversation_type: "sms",
            contact_id: null,
            user_id: null,
            display_name: "Phone contact",
            avatar_url: null,
            masked_phone: "+63****4567",
            is_contact: false,
            last_message_at: "2026-11-11T00:00:00Z",
          },
        ]),
        [`DELETE ${BASE}/recent`]: { status: 204 },
      }),
    );
    const user = userEvent.setup();
    renderApp("/contacts");
    await user.click(await screen.findByRole("button", { name: "Recent" }));
    expect(await screen.findByText("Recent conversations")).toBeInTheDocument();
    expect(screen.getByText("SMS · +63****4567")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear list" }));
    await waitFor(() => expect(api.callsTo("DELETE", `${BASE}/recent`)).toHaveLength(1));
  });

  it("changes discovery settings from the settings page", async () => {
    const privacy = {
      profile_visibility: "contacts",
      share_presence: "contacts",
      show_last_seen: false,
      discoverable_by_email: false,
      discoverable_by_phone: false,
    };
    const api = mockApi({
      ...signedInRoutes(),
      "GET /api/v1/auth/sessions": ok([]),
      "GET /api/v1/users/me/phone": ok({
        verified: false,
        masked: null,
        verification_mode: null,
        verified_at: null,
        delivery_mode: "simulated",
      }),
      "GET /api/v1/users/me/privacy": ok(privacy),
      "PATCH /api/v1/users/me/privacy": ok({ ...privacy, discoverable_by_email: true }),
    });
    const user = userEvent.setup();
    renderApp("/settings/profile");
    const box = await screen.findByRole("checkbox", {
      name: /Let people find me by my email address/,
    });
    expect(box).not.toBeChecked();
    await user.click(box);
    await waitFor(() => expect(api.callsTo("PATCH", "/api/v1/users/me/privacy")).toHaveLength(1));
    expect(api.callsTo("PATCH", "/api/v1/users/me/privacy")[0]?.body).toEqual({
      discoverable_by_email: true,
    });
    await waitFor(() => expect(box).toBeChecked());
  });
});
