import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { sessionStore } from "@/lib/auth/session";
import { fail, makeProfile, mockApi, ok, signedInRoutes, type MockRequest } from "@/test/api-mock";
import { renderApp } from "@/test/render-app";

const SESSIONS = [
  {
    id: "s1",
    created_at: "2026-11-10T00:00:00Z",
    last_active_at: "2026-11-11T00:00:00Z",
    device: "Chrome on Windows",
    ip_prefix: "203.0.113.0/24",
    current: true,
  },
  {
    id: "s2",
    created_at: "2026-11-09T00:00:00Z",
    last_active_at: "2026-11-10T00:00:00Z",
    device: "Safari on iPhone",
    ip_prefix: null,
    current: false,
  },
];

function settingsRoutes(extra: Record<string, Parameters<typeof mockApi>[0][string]> = {}) {
  return {
    ...signedInRoutes(),
    "GET /api/v1/auth/sessions": ok(SESSIONS),
    "GET /api/v1/users/me/phone": ok({
      verified: false,
      masked: null,
      verification_mode: null,
      verified_at: null,
      delivery_mode: "simulated",
    }),
    ...extra,
  };
}

describe("profile setup", () => {
  const pending = makeProfile({
    onboarding_completed: false,
    username: null,
    display_name: "New user",
    time_zone: "UTC",
  });

  it("validates the username before sending", async () => {
    const api = mockApi(signedInRoutes(pending));
    const user = userEvent.setup();
    renderApp("/onboarding");
    await user.type(await screen.findByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Display name"), "Marites");
    await user.click(screen.getByRole("button", { name: "Finish setup" }));
    expect(await screen.findByText("This username is reserved.")).toBeInTheDocument();
    expect(api.callsTo("POST", "/api/v1/users/me/onboarding")).toHaveLength(0);
  });

  it("offers suggestions when the username is taken and finishes with one", async () => {
    let attempts = 0;
    const api = mockApi({
      ...signedInRoutes(pending),
      "POST /api/v1/users/me/onboarding": (request: MockRequest) => {
        attempts += 1;
        return attempts === 1
          ? fail(409, "username_taken", "That username is taken.", {
              suggestions: ["marites42", "marites7"],
            })
          : ok(makeProfile({ username: (request.body as { username: string }).username }));
      },
    });
    const user = userEvent.setup();
    const { router } = renderApp("/onboarding");
    await user.type(await screen.findByLabelText("Username"), "marites");
    await user.type(screen.getByLabelText("Display name"), "Marites Santos");
    await user.click(screen.getByRole("button", { name: "Finish setup" }));

    expect(await screen.findByText("That username is taken.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "marites42" }));
    await user.click(screen.getByRole("button", { name: "Finish setup" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    const sent = api.callsTo("POST", "/api/v1/users/me/onboarding")[1]?.body as Record<
      string,
      unknown
    >;
    expect(sent.username).toBe("marites42");
    expect(sent.display_name).toBe("Marites Santos");
  });
});

describe("profile settings", () => {
  it("sends only changed fields and confirms the save", async () => {
    const api = mockApi(
      settingsRoutes({
        "PATCH /api/v1/users/me": (request: MockRequest) =>
          ok(makeProfile({ ...(request.body as object), updated_at: "2026-11-11T01:00:00Z" })),
      }),
    );
    const user = userEvent.setup();
    renderApp("/settings/profile");
    const bio = await screen.findByLabelText("Bio or status message");
    await user.type(bio, "OFW in <b>Dubai</b>");
    await user.selectOptions(screen.getByLabelText("Interface"), "classic");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Profile saved.")).toBeInTheDocument();
    expect(api.callsTo("PATCH", "/api/v1/users/me")[0]?.body).toEqual({
      bio: "OFW in Dubai",
      ui_mode: "classic",
    });
    // The saved interface mode is applied to the whole app.
    await waitFor(() => expect(document.documentElement.dataset.mode).toBe("classic"));
  });

  it("validates the bio length and display name", async () => {
    const api = mockApi(settingsRoutes());
    const user = userEvent.setup();
    renderApp("/settings/profile");
    const name = await screen.findByLabelText("Display name");
    await user.clear(name);
    await user.type(name, "M");
    await user.click(screen.getByLabelText("Bio or status message"));
    await user.paste("x".repeat(161));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Use at most 160 characters.")).toBeInTheDocument();
    expect(screen.getByText("Use at least 2 characters.")).toBeInTheDocument();
    expect(api.callsTo("PATCH", "/api/v1/users/me")).toHaveLength(0);
  });

  it("shows the username and email as read-only", async () => {
    mockApi(settingsRoutes());
    renderApp("/settings/profile");
    expect(await screen.findByLabelText("Username")).toBeDisabled();
    expect(screen.getByLabelText("Email")).toHaveValue("marites@example.com");
  });

  it("refreshes an expired access token once and retries", async () => {
    let meCalls = 0;
    const api = mockApi({
      ...settingsRoutes(),
      "GET /api/v1/users/me": () => {
        meCalls += 1;
        return meCalls === 1
          ? fail(401, "token_expired", "Your session has expired.")
          : ok(makeProfile());
      },
    });
    renderApp("/settings/profile");
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(api.callsTo("POST", "/api/v1/auth/refresh").length).toBeGreaterThanOrEqual(2);
    expect(api.callsTo("POST", "/api/v1/auth/refresh")[1]?.headers["X-Chikka-CSRF"]).toBe("1");
  });

  it("returns to sign in when the session cannot be renewed", async () => {
    let refreshes = 0;
    mockApi({
      ...settingsRoutes(),
      "POST /api/v1/auth/refresh": () => {
        refreshes += 1;
        return refreshes === 1
          ? ok({ access_token: "a", token_type: "bearer", expires_in: 1 })
          : fail(401, "not_authenticated");
      },
      "GET /api/v1/users/me": fail(401, "session_revoked", "Your session has ended."),
    });
    const { router } = renderApp("/settings/profile");
    await waitFor(() => expect(router.state.location.pathname).toBe("/auth/sign-in"));
    expect(sessionStore.getSnapshot().status).toBe("signed-out");
  });
});

describe("mobile number", () => {
  it("shows the code in a SIMULATED inbox and verifies the number", async () => {
    const api = mockApi(
      settingsRoutes({
        "POST /api/v1/users/me/phone": ok({
          masked: "+63****0001",
          verification_mode: "simulated",
          expires_in: 600,
          resend_available_in: 60,
        }),
        "GET /api/v1/users/me/phone/simulated-inbox": ok([
          {
            label: "SIMULATED",
            to: "+63****0001",
            body: "Your Chikka Reborn code is 482913. It expires in 10 minutes.",
            created_at: "2026-11-11T00:00:00Z",
            expires_at: "2026-11-11T00:10:00Z",
          },
        ]),
        "POST /api/v1/users/me/phone/verify": ok({
          verified: true,
          masked: "+63****0001",
          verification_mode: "simulated",
          verified_at: "2026-11-11T00:01:00Z",
          delivery_mode: "simulated",
        }),
      }),
    );
    const user = userEvent.setup();
    renderApp("/settings/profile");
    expect(
      await screen.findByText(/Simulation mode: no real text message is sent/),
    ).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "Mobile number" }), "+63 917 123 0001");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    const inbox = await screen.findByRole("region", { name: /Simulated SMS inbox/ });
    expect(within(inbox).getAllByText("SIMULATED").length).toBeGreaterThan(0);
    expect(await within(inbox).findByText(/482913/)).toBeInTheDocument();
    expect(api.callsTo("POST", "/api/v1/users/me/phone")[0]?.body).toEqual({
      phone_number: "+639171230001",
    });

    await user.type(screen.getByLabelText("Verification code"), "482913");
    await user.click(screen.getByRole("button", { name: "Verify number" }));
    expect(await screen.findByText("+63****0001")).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();
  });

  it("shows the server's message for a wrong code", async () => {
    mockApi(
      settingsRoutes({
        "POST /api/v1/users/me/phone": ok({
          masked: "+63****0001",
          verification_mode: "simulated",
          expires_in: 600,
          resend_available_in: 60,
        }),
        "GET /api/v1/users/me/phone/simulated-inbox": ok([]),
        "POST /api/v1/users/me/phone/verify": fail(
          422,
          "otp_invalid",
          "That code is not correct.",
          { attempts_remaining: 4 },
        ),
      }),
    );
    const user = userEvent.setup();
    renderApp("/settings/profile");
    await user.type(await screen.findByRole("textbox", { name: "Mobile number" }), "+639171230001");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await user.type(await screen.findByLabelText("Verification code"), "000000");
    await user.click(screen.getByRole("button", { name: "Verify number" }));
    expect(await screen.findByText("That code is not correct.")).toBeInTheDocument();
  });

  it("rejects numbers without a country code in the browser", async () => {
    const api = mockApi(settingsRoutes());
    const user = userEvent.setup();
    renderApp("/settings/profile");
    await user.type(await screen.findByRole("textbox", { name: "Mobile number" }), "09171230001");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findByText(/Use international format/)).toBeInTheDocument();
    expect(api.callsTo("POST", "/api/v1/users/me/phone")).toHaveLength(0);
  });
});

describe("photo and presence", () => {
  it("rejects unsupported and oversized files before uploading", async () => {
    const api = mockApi(settingsRoutes());
    const user = userEvent.setup({ applyAccept: false });
    renderApp("/settings/profile");
    const input = await screen.findByLabelText("Choose a profile photo");
    await user.upload(input, new File(["gif"], "a.gif", { type: "image/gif" }));
    expect(await screen.findByText("Use a JPEG, PNG or WebP image.")).toBeInTheDocument();
    await user.upload(
      input,
      new File([new Uint8Array(2 * 1024 * 1024 + 1)], "big.png", { type: "image/png" }),
    );
    expect(await screen.findByText("The image must be 2 MB or smaller.")).toBeInTheDocument();
    expect(api.callsTo("POST", "/api/v1/users/me/avatar")).toHaveLength(0);
  });

  it("uploads a photo as multipart form data", async () => {
    const api = mockApi(
      settingsRoutes({
        "POST /api/v1/users/me/avatar": ok({ avatar_url: "https://storage.example.com/a.webp" }),
      }),
    );
    const user = userEvent.setup();
    renderApp("/settings/profile");
    await user.upload(
      await screen.findByLabelText("Choose a profile photo"),
      new File(["png"], "me.png", { type: "image/png" }),
    );
    expect(await screen.findByText("Photo updated.")).toBeInTheDocument();
    const call = api.callsTo("POST", "/api/v1/users/me/avatar")[0];
    expect(call?.body).toBeInstanceOf(FormData);
    expect(call?.headers["Content-Type"]).toBeUndefined();
  });

  it("changes the presence preference", async () => {
    const api = mockApi(
      settingsRoutes({
        "PUT /api/v1/users/me/presence": ok({
          status: "busy",
          preference: "busy",
          last_seen_at: null,
        }),
      }),
    );
    const user = userEvent.setup();
    renderApp("/settings/profile");
    await user.click(await screen.findByRole("radio", { name: /Busy/ }));
    await waitFor(() =>
      expect(api.callsTo("PUT", "/api/v1/users/me/presence")[0]?.body).toEqual({
        preference: "busy",
      }),
    );
    expect(api.callsTo("POST", "/api/v1/users/me/presence/heartbeat").length).toBeGreaterThan(0);
  });
});

describe("sessions and account deletion", () => {
  it("lists sessions and signs out another device", async () => {
    const api = mockApi(settingsRoutes({ "DELETE /api/v1/auth/sessions/s2": { status: 204 } }));
    const user = userEvent.setup();
    renderApp("/settings/profile");
    expect(await screen.findByText("This device")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sign out Safari on iPhone" }));
    await waitFor(() => expect(api.callsTo("DELETE", "/api/v1/auth/sessions/s2")).toHaveLength(1));
  });

  it("requires DELETE and the password, and reports a wrong password", async () => {
    const api = mockApi(
      settingsRoutes({
        "DELETE /api/v1/users/me": fail(
          403,
          "reauthentication_failed",
          "The password is incorrect.",
        ),
      }),
    );
    const user = userEvent.setup();
    renderApp("/settings/profile");
    await user.click(await screen.findByRole("button", { name: "Delete account…" }));
    await user.type(screen.getByLabelText("Your password"), "Wrong-Pass-1");
    await user.type(screen.getByLabelText("Type DELETE to confirm"), "delete");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    expect(await screen.findByText("Type DELETE in capital letters.")).toBeInTheDocument();
    expect(api.callsTo("DELETE", "/api/v1/users/me")).toHaveLength(0);

    const phrase = screen.getByLabelText("Type DELETE to confirm");
    await user.clear(phrase);
    await user.type(phrase, "DELETE");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    expect(
      await screen.findByText("The password is incorrect. Nothing was deleted."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Your password")).toHaveValue("");
  });

  it("deletes the account, signs out and leaves", async () => {
    const api = mockApi(
      settingsRoutes({
        "DELETE /api/v1/users/me": {
          status: 202,
          body: {
            data: { message: "deleted", deleted_at: "2026-11-11T00:00:00Z" },
            request_id: "r",
          },
        },
      }),
    );
    const user = userEvent.setup();
    const { router } = renderApp("/settings/profile");
    await user.click(await screen.findByRole("button", { name: "Delete account…" }));
    await user.type(screen.getByLabelText("Your password"), "Correct-Horse-7");
    await user.type(screen.getByLabelText("Type DELETE to confirm"), "DELETE");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/auth/sign-in"));
    expect(api.callsTo("DELETE", "/api/v1/users/me")[0]?.body).toEqual({
      password: "Correct-Horse-7",
      confirmation: "DELETE",
    });
    expect(sessionStore.getSnapshot().status).toBe("signed-out");
  });
});
