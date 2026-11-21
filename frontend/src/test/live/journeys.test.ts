// @vitest-environment node
/**
 * Integration review: the five critical user journeys, driven through the frontend's own
 * service layer (API client, session store, real-time client) against the real backend, a real
 * PostgreSQL schema with every migration and RLS, and the simulated SMS provider.
 * Started by scripts/e2e-local.ps1. Skipped otherwise. Fictional data only.
 */
import { describe, expect, it } from "vitest";
import {
  API,
  FAKE,
  PASSWORD,
  errorOf,
  newBrowser,
  sharedAdmin,
  signUp,
  until,
  uniqueName,
  type Person,
} from "@/test/live/helpers";
import type { Balance } from "@/features/credits/types";
import type { SmsMessage } from "@/features/sms/types";

const ALL_STATUSES = ["queued", "retrying", "accepted", "sent", "delivered"];
const RANK: Record<string, number> = { queued: 0, retrying: 1, accepted: 2, sent: 3, delivered: 4 };

function active(balance: Balance) {
  const ledger = balance.ledgers.find((l) => l.ledger === balance.active_ledger);
  if (!ledger) throw new Error("no active ledger");
  return ledger;
}

function fictionalMobile(): string {
  // +63 917 xxx xxxx: a fictional Philippine mobile number.
  return `+63917${String(Date.now() % 10_000_000).padStart(7, "0")}`;
}

describe.skipIf(!API || !FAKE)("journey 1: a new user", () => {
  it("registers, confirms the email, completes the profile and reaches the dashboard", async () => {
    const browser = newBrowser();
    const username = uniqueName("newbie").toLowerCase().slice(0, 20);
    const email = `${username}@example.com`;

    const registered = await browser.auth.register({
      email,
      display_name: "New Person",
      password: PASSWORD,
      accept_terms: true,
    });
    expect(registered.message).toMatch(/confirm/i);

    // Cannot get in before confirming.
    expect((await errorOf(browser.auth.login({ email, password: PASSWORD }))).code).toBe(
      "email_not_verified",
    );

    const { emailToken } = await import("@/test/live/helpers");
    browser.session.signIn(await browser.auth.verifyEmail(await emailToken(email, "signup")));

    // Route guards in the SPA send an un-onboarded user to /onboarding.
    const pending = await browser.profile.getMe();
    expect(pending).toMatchObject({ status: "active", onboarding_completed: false });

    const done = await browser.profile.completeOnboarding({
      username,
      display_name: "New Person",
      country_code: "PH",
      language: "en",
      time_zone: "Asia/Manila",
      ui_mode: "classic",
    });
    expect(done).toMatchObject({ username, onboarding_completed: true, ui_mode: "classic" });

    // What the dashboard loads on arrival: all of these must answer for a new user.
    const credits = await browser.credits.balance();
    expect(active(credits).charges_apply).toBe(true);
    expect((await browser.notifications.unreadCount()).unread_count).toBeGreaterThanOrEqual(0);
    expect((await browser.chat.unread()).unread_messages).toBe(0);
    expect((await browser.sms.status()).mode).toBe("simulation");
    expect((await browser.contacts.list({ filter: "all", page: 1 })).data).toEqual([]);

    // Switching interface (header toggle) is saved to the profile and follows the user.
    expect((await browser.profile.updateMe({ ui_mode: "modern" })).ui_mode).toBe("modern");

    // The saved preference survives a fresh sign-in on another device.
    const second = newBrowser();
    second.session.signIn(await second.auth.login({ email, password: PASSWORD }));
    expect((await second.profile.getMe()).ui_mode).toBe("modern");

    // Signing out everywhere ends every device at once: the other browser is refused and its
    // session store falls back to signed-out (the SPA then shows the sign-in page).
    await browser.auth.logout("global");
    expect((await errorOf(second.profile.getMe())).status).toBe(401);
    expect(second.session.getSnapshot().status).toBe("signed-out");
  });
});

describe.skipIf(!API || !FAKE)("journey 2: Chikka to Chikka messaging", () => {
  it("adds a contact, chats in real time and keeps the same history for both", async () => {
    const [ana, ben] = [await signUp("ana"), await signUp("ben")];
    const benSocket = await ben.listen();
    const anaSocket = await ana.listen();

    // A finds B by exact username and sends a request; B sees and accepts it.
    const found = await ana.contacts.search(ben.username);
    const person = found.people.find((p) => p.username === ben.username);
    expect(person?.relationship).toBe("none");
    await ana.contacts.sendRequest(person?.user_id ?? "", "Hi Ben, it's Ana");

    // Nobody can chat before the request is accepted.
    expect((await errorOf(ana.chat.open(ben.userId))).status).toBeGreaterThanOrEqual(400);

    const incoming = await ben.contacts.requests("incoming", 1);
    expect(incoming.data).toHaveLength(1);
    expect(incoming.data[0]?.person.user_id).toBe(ana.userId);
    await ben.contacts.accept(incoming.data[0]?.id ?? "");

    const anaBuddies = (await ana.contacts.list({ filter: "all", page: 1 })).data;
    const benBuddies = (await ben.contacts.list({ filter: "all", page: 1 })).data;
    expect(anaBuddies.map((c) => c.user_id)).toEqual([ben.userId]);
    expect(benBuddies.map((c) => c.user_id)).toEqual([ana.userId]);

    // A starts a conversation and sends.
    const conversation = await ana.chat.open(ben.userId);
    const again = await ana.chat.open(ben.userId);
    expect(again.id).toBe(conversation.id);
    const clientId = crypto.randomUUID();
    const sent = await ana.chat.send(conversation.id, {
      client_message_id: clientId,
      body: "Kumusta, Ben!",
    });
    expect(sent).toMatchObject({ body: "Kumusta, Ben!", is_mine: true, status: "sent" });
    // A retry with the same client id does not duplicate.
    const retried = await ana.chat.send(conversation.id, {
      client_message_id: clientId,
      body: "Kumusta, Ben!",
    });
    expect(retried.id).toBe(sent.id);

    // B receives it in real time, without polling.
    const pushed = await until(async () => {
      return benSocket.events.find((e) => e.type === "message.created");
    }, "Ben to receive the message over the socket");
    expect((pushed.data as { message: { body: string } }).message.body).toBe("Kumusta, Ben!");

    // B sees it in the list, as unread, with a notification.
    const benList = await ben.chat.list({ archived: false, q: "" });
    expect(benList.data[0]?.unread_count).toBe(1);
    expect((await ben.chat.unread()).unread_messages).toBe(1);
    const feed = await ben.notifications.feed(1, false);
    expect(feed.data.some((n) => n.type === "new_message")).toBe(true);
    expect(JSON.stringify(feed)).not.toContain("Kumusta");

    // B opens, reads, and replies.
    const benThread = await ben.chat.messages(conversation.id, {});
    expect(benThread.messages.map((m) => m.body)).toEqual(["Kumusta, Ben!"]);
    await ben.chat.markRead(conversation.id, benThread.messages.at(-1)?.seq ?? 0);
    expect((await ben.chat.unread()).unread_messages).toBe(0);
    await ben.chat.send(conversation.id, {
      client_message_id: crypto.randomUUID(),
      body: "Uy Ana! Kumusta ka?",
    });

    // A gets the reply live, and A's own message shows as delivered (the sender's status).
    await until(async () => {
      return anaSocket.events.filter((e) => e.type === "message.created").length >= 1;
    }, "Ana to receive the reply over the socket");
    const status = await until(async () => {
      return anaSocket.events.find((e) => e.type === "message.status_changed");
    }, "Ana to learn the message was delivered");
    expect((status.data as { status: string }).status).toMatch(/delivered|read/);

    // Both see the same ordered history.
    const history = async (p: Person) =>
      (await p.chat.messages(conversation.id, {})).messages.map((m) => [m.body, m.is_mine]);
    expect(await history(ana)).toEqual([
      ["Kumusta, Ben!", true],
      ["Uy Ana! Kumusta ka?", false],
    ]);
    expect(await history(ben)).toEqual([
      ["Kumusta, Ben!", false],
      ["Uy Ana! Kumusta ka?", true],
    ]);

    // A stranger cannot read or write it.
    const eve = await sharedAdmin(); // an administrator is still not a participant
    expect((await errorOf(eve.chat.get(conversation.id))).status).toBe(404);
    expect(
      (
        await errorOf(
          eve.chat.send(conversation.id, { client_message_id: crypto.randomUUID(), body: "hi" }),
        )
      ).status,
    ).toBeGreaterThanOrEqual(403);

    benSocket.stop();
    anaSocket.stop();
  });
});

describe.skipIf(!API || !FAKE)("journey 3: SMS", () => {
  it("quotes, sends in simulation, tracks delivery, and shows the reply in the same thread", async () => {
    const user = await signUp("sam");
    const mobile = fictionalMobile();

    // A mobile number is verified first (simulation: the code is shown in the simulated inbox).
    const started = await user.profile.startPhone(mobile);
    expect(started.verification_mode).toBe("simulated");
    const inbox = await user.profile.simulatedInbox();
    expect(inbox[0]?.label).toBe("SIMULATED");
    const code = /\b(\d{6})\b/.exec(inbox[0]?.body ?? "")?.[1];
    expect(code).toBeDefined();
    await user.profile.confirmPhone(mobile, code ?? "");

    // The user picks an external number; the app shows segments and cost first.
    const target = { kind: "number", to: "+639181234567", countryCode: "PH" } as const;
    const countries = await user.sms.countries();
    expect(countries.find((c) => c.country_code === "PH")).toBeDefined();
    const before = await user.credits.balance();
    const quote = await user.sms.quote(target, "Kumusta ka, Nanay?");
    expect(quote.is_simulated).toBe(true);
    expect(quote.segment).toMatchObject({ segments: 1, encoding: "gsm7" });
    expect(quote.cost.credits).not.toBeNull();
    expect(quote.consent.required).toBe(true);
    expect(quote.can_send).toBe(false); // consent first

    // Sending without the user's consent is refused by the server too.
    expect(
      (await errorOf(user.sms.send(target, "Kumusta ka, Nanay?", crypto.randomUUID()))).code,
    ).toBe("consent_required");

    await user.sms.setConsent(target, "granted");
    expect((await user.sms.quote(target, "Kumusta ka, Nanay?")).can_send).toBe(true);

    // The user approves; the same key twice sends once.
    const live = await user.listen();
    const key = crypto.randomUUID();
    const sent = await user.sms.send(target, "Kumusta ka, Nanay?", key);
    const duplicate = await user.sms.send(target, "Kumusta ka, Nanay?", key);
    expect(duplicate.id).toBe(sent.id);
    expect(sent.is_simulated).toBe(true);
    expect(sent.status).toBe("queued");

    // The status only moves forward, and "delivered" is reached through accepted and sent.
    const seen: string[] = [];
    const delivered = await until(
      async () => {
        const thread = await user.sms.messages(sent.conversation_id);
        const message = thread.messages.find((m) => m.id === sent.id);
        if (message && seen.at(-1) !== message.status) seen.push(message.status);
        return message?.status === "delivered" ? message : null;
      },
      "the simulated message to be delivered",
      30_000,
    );
    expect(delivered.is_simulated).toBe(true);
    const ranks = seen.map((s) => RANK[s] ?? -1);
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
    expect(seen.every((s) => ALL_STATUSES.includes(s))).toBe(true);
    expect(seen).toContain("accepted");

    // The same changes were pushed over the socket, in order, and never ahead of REST.
    const pushedStatuses = () =>
      live.events
        .filter((e) => e.type.startsWith("sms.message."))
        .map((e) => (e.data as { message: SmsMessage }).message.status);
    await until(
      async () => pushedStatuses().includes("delivered"),
      "the delivered status to be pushed over the socket",
      10_000,
    );
    expect(pushedStatuses().indexOf("delivered")).toBeGreaterThan(
      pushedStatuses().indexOf("accepted"),
    );

    // Demo credits were spent once, for one message, never the live ledger.
    const after = await user.credits.balance();
    expect(active(after).available_units).toBeLessThan(active(before).available_units);
    const spent = active(before).available_units - active(after).available_units;
    expect(spent).toBe(quote.cost.units);
    const history = await user.credits.transactions(1);
    expect(history.data.length).toBeGreaterThan(0);

    // The external user replies (an administrator uses the signed simulation path).
    const admin = await sharedAdmin();
    await admin.adminSms.simulateInbound({
      from_phone: "+639181234567",
      body: "Okay sige anak.",
    });

    // The reply lands in the same conversation thread, labelled simulated and unread.
    const thread = await until(async () => {
      const t = await user.sms.messages(sent.conversation_id);
      return t.messages.some((m: SmsMessage) => m.direction === "inbound") ? t : null;
    }, "the reply to appear in the same SMS conversation");
    expect(thread.messages.map((m) => [m.direction, m.body])).toEqual([
      ["outbound", "Kumusta ka, Nanay?"],
      ["inbound", "Okay sige anak."],
    ]);
    expect(thread.messages[1]?.is_simulated).toBe(true);
    const conversations = await user.sms.conversations();
    expect(conversations.data.filter((c) => c.id === sent.conversation_id)).toHaveLength(1);
    expect(conversations.data[0]?.unread_count).toBe(1);
    const feed = await user.notifications.feed(1, false);
    expect(feed.data.some((n) => n.type === "sms_inbound")).toBe(true);
    live.stop();
  });
});

describe.skipIf(!API || !FAKE)("journey 4: AI assistance", () => {
  it("translates into a draft, records the decision, and sends only after the user does", async () => {
    const [ana, ben] = [await signUp("aia"), await signUp("aib")];
    const person = (await ana.contacts.search(ben.username)).people[0];
    await ana.contacts.sendRequest(person?.user_id ?? "", null);
    await ben.contacts.accept((await ben.contacts.requests("incoming", 1)).data[0]?.id ?? "");
    const conversation = await ana.chat.open(ben.userId);

    // Off until the user turns it on.
    expect((await ana.ai.status()).enabled).toBe(false);
    expect(
      (
        await errorOf(
          ana.ai.run({ kind: "translate", text: "Good morning", target: "fil", source: "en" }),
        )
      ).status,
    ).toBeGreaterThanOrEqual(400);
    await ana.ai.setEnabled(true);

    const draft = await ana.ai.run({
      kind: "translate",
      text: "Good morning",
      target: "fil",
      source: "en",
    });
    expect(draft.texts.length).toBe(1);
    expect(draft.simulated).toBe(true);

    // Nothing has been sent yet: a draft is not a message.
    expect((await ana.chat.messages(conversation.id, {})).messages).toEqual([]);
    expect((await ben.chat.messages(conversation.id, {})).messages).toEqual([]);

    // The user edits the draft, records that, and sends over the channel of this conversation.
    const edited = `${draft.texts[0]} po`;
    await ana.ai.recordDecision(draft.assistanceId ?? "", "edited");
    const sent = await ana.chat.send(conversation.id, {
      client_message_id: crypto.randomUUID(),
      body: edited,
    });
    expect(sent.body).toBe(edited);
    expect((await ben.chat.messages(conversation.id, {})).messages.map((m) => m.body)).toEqual([
      edited,
    ]);
    // It travelled as a Chikka message: no SMS exists for either person.
    expect((await ana.sms.conversations()).data).toEqual([]);
    expect((await ben.sms.conversations()).data).toEqual([]);

    // The model's input and output are not kept; only metadata is.
    const root = await sharedAdmin();
    const metrics = await root.admin.aiMetrics();
    expect(metrics.total_requests).toBeGreaterThan(0);
    expect(JSON.stringify(metrics)).not.toContain("Good morning");

    // Reply suggestions come from the conversation, are drafts, and send nothing.
    const replies = await ana.ai.run({ kind: "replies", conversationId: conversation.id });
    expect(replies.texts.length).toBeGreaterThan(0);
    expect((await ben.chat.messages(conversation.id, {})).messages).toHaveLength(1);
  });
});

describe.skipIf(!API || !FAKE)("journey 5: administration", () => {
  it("reviews SMS delivery, investigates a failed message and finds its audit record", async () => {
    const user = await signUp("fail");
    const mobile = fictionalMobile();
    await user.profile.startPhone(mobile);
    const code = /\b(\d{6})\b/.exec((await user.profile.simulatedInbox())[0]?.body ?? "")?.[1];
    await user.profile.confirmPhone(mobile, code ?? "");

    // +1 202 555 0101 is reserved by the simulator to fail.
    const target = { kind: "number", to: "+12025550101", countryCode: "US" } as const;
    await user.sms.setConsent(target, "granted");
    const quote = await user.sms.quote(target, "This one will fail");
    expect(quote.can_send, JSON.stringify(quote.blockers)).toBe(true);
    const balanceBefore = await user.credits.balance();
    const sent = await user.sms.send(target, "This one will fail", crypto.randomUUID());

    const failed = await until(
      async () => {
        const thread = await user.sms.messages(sent.conversation_id);
        const m = thread.messages.find((x) => x.id === sent.id);
        return m && ["failed", "undelivered"].includes(m.status) ? m : null;
      },
      "the message to fail",
      30_000,
    );
    // The user sees a readable reason; the message is never presented as delivered.
    expect(failed.status).not.toBe("delivered");
    expect(failed.failure?.reason).toBeTruthy();
    // A failed message is refunded: the balance returns.
    const balanceAfter = await until(async () => {
      const b = await user.credits.balance();
      return active(b).available_units === active(balanceBefore).available_units ? b : null;
    }, "the credits to be refunded");
    expect(active(balanceAfter).reserved_units ?? 0).toBe(0);
    expect(
      (await user.notifications.feed(1, false)).data.some((n) => n.type === "sms_failed"),
    ).toBe(true);

    // Ordinary users are refused, and that refusal is itself audited.
    expect((await errorOf(user.admin.dashboard())).status).toBe(403);

    const admin = await sharedAdmin();
    const dashboard = await admin.admin.dashboard();
    expect(dashboard.users.total_registered).toBeGreaterThanOrEqual(2);
    expect(dashboard.sms.simulated.failed + dashboard.sms.simulated.undelivered).toBeGreaterThan(0);
    // Simulated traffic is never counted as live.
    expect(dashboard.sms.live.sent).toBe(0);

    const list = await admin.admin.smsMessages({ direction: "outbound" });
    const row = list.data.find((m) => m.id === sent.id);
    expect(row).toBeDefined();
    expect(row?.is_simulated).toBe(true);
    // The admin list masks the number and never carries the body.
    expect(JSON.stringify(row)).not.toContain("2025550101");
    expect(JSON.stringify(row)).not.toContain("This one will fail");

    const detail = await admin.admin.smsMessage(sent.id);
    expect(detail.failure_reason ?? detail.attempts_history.at(-1)?.failure_reason).toBeTruthy();
    expect(detail.attempts_history.length).toBeGreaterThan(0);
    expect(detail.status).not.toBe("delivered");

    const health = await admin.admin.providers();
    expect(health.configuration.sms_provider_mode).toBe("mock");
    expect(JSON.stringify(health)).not.toMatch(/auth_token|secret/i);

    // Looking at the message is itself on the audit trail, and so is the denied attempt.
    const audit = await until(async () => {
      const page = await admin.admin.auditLogs({});
      return page.data.some((r) => r.action.includes("sms")) ? page : null;
    }, "SMS audit records");
    const actions = audit.data.map((r) => r.action);
    expect(actions.some((a) => a.startsWith("sms."))).toBe(true);
    const denied = await admin.admin.auditLogs({ outcome: "denied" });
    expect(denied.data.some((r) => r.actor_id === user.userId)).toBe(true);
    expect(JSON.stringify(audit)).not.toContain("+12025550101");
    expect(JSON.stringify(audit)).not.toContain("This one will fail");
  });
});
