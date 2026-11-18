import type { Page } from "@playwright/test";
import { API } from "./support/stack";
import { apiGet, bearer, createUser, promoteToAdmin } from "./support/api";
import { browserUser, type Person } from "./support/people";
import { expect, test } from "./support/fixtures";

const CONSENT = /I have this person's permission to text them/;

async function composeSms(
  page: Page,
  options: { countryCode?: string; number: string; body: string; consent?: boolean },
): Promise<void> {
  await page.goto("/sms/new");
  await expect(page.getByText("SIMULATED").first()).toBeVisible();
  if (options.countryCode) await page.getByLabel("Country").selectOption(options.countryCode);
  await page.getByLabel("Mobile number").fill(options.number);
  await page.getByLabel("Message").fill(options.body);
  if (options.consent ?? true) {
    // The checkbox mirrors the server's recorded consent, so it flips after the request returns.
    await page.getByLabel(CONSENT).click();
    await expect(page.getByLabel(CONSENT)).toBeChecked();
  }
}

async function reviewAndSend(page: Page): Promise<void> {
  const review = page.getByRole("button", { name: "Review and send" });
  await expect(review).toBeEnabled();
  await review.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("SIMULATED")).toBeVisible();
  await expect(dialog.getByText(/no real SMS will be sent/)).toBeVisible();
  await dialog.getByRole("button", { name: "Send SMS" }).click();
  await expect(page).toHaveURL(/\/sms\/[0-9a-f-]{36}/);
}

async function smsUser(page: Page, label: string): Promise<Person> {
  const person = await browserUser(page, label);
  await person.verifyPhone();
  return person;
}

async function simulateReply(page: Page, from: string, body: string, replayId?: string) {
  const admin = await createUser(page.request, "root");
  await promoteToAdmin(page.request, admin);
  // A fresh login so the promotion is reflected; the admin is only an API caller here.
  const login = await page.request.post(`${API}/api/v1/auth/login`, {
    data: { email: admin.email, password: "Correct-Horse-7" },
  });
  admin.accessToken = (
    (await login.json()) as { data: { access_token: string } }
  ).data.access_token;
  const response = await page.request.post(`${API}/api/v1/admin/sms/simulate/inbound`, {
    headers: bearer(admin),
    data: { from_phone: from, body, to_number: null, replay_id: replayId ?? null },
  });
  return { admin, response };
}

test.describe("simulated SMS", () => {
  test("sends a simulated SMS after confirmation and tracks it to delivered", async ({ page }) => {
    const sam = await smsUser(page, "sam");
    const before = await apiGet<{ data: { ledgers: { available_units: number }[] } }>(
      page.request,
      sam.user,
      "/api/v1/credits",
    );

    await composeSms(page, { number: "0918 123 4567", body: "Kumusta ka, Nanay?" });
    // The cost and segment count are shown before anything is sent.
    await expect(page.getByText(/1 segment/)).toBeVisible();
    await expect(page.getByText(/Estimated .* demo credits/)).toBeVisible();

    // Nothing is sent until the confirmation dialog is accepted.
    expect((await sam.api.get<{ data: unknown[] }>("/api/v1/sms/conversations")).data).toEqual([]);
    await reviewAndSend(page);

    const thread = page.getByRole("log", { name: "SMS messages" });
    await expect(thread.getByText("Kumusta ka, Nanay?")).toBeVisible();
    await expect(thread.getByText("SIMULATED").first()).toBeVisible();
    // "Accepted" is never shown as "Delivered": the final state arrives only after the callback.
    await expect(thread.getByText("Delivered", { exact: false }).first()).toBeVisible({
      timeout: 45_000,
    });

    const after = await apiGet<{ data: { ledgers: { available_units: number }[] } }>(
      page.request,
      sam.user,
      "/api/v1/credits",
    );
    const sum = (r: typeof before) => r.data.ledgers.reduce((n, l) => n + l.available_units, 0);
    expect(sum(after)).toBeLessThan(sum(before));
  });

  test("a reply from the other phone appears in the same thread, labelled simulated", async ({
    page,
  }) => {
    const sam = await smsUser(page, "rep");
    await composeSms(page, { number: "0918 765 4321", body: "Ingat ka." });
    await reviewAndSend(page);
    const thread = page.getByRole("log", { name: "SMS messages" });
    await expect(thread.getByText("Ingat ka.")).toBeVisible();

    const { response } = await simulateReply(page, "+639187654321", "Okay sige anak.");
    expect(response.status(), await response.text()).toBe(200);

    // It arrives live, in the same conversation.
    await expect(thread.getByText("Okay sige anak.")).toBeVisible({ timeout: 20_000 });
    const conversations = await sam.api.get<{ data: { id: string }[] }>(
      "/api/v1/sms/conversations",
    );
    expect(conversations.data).toHaveLength(1);

    // A repeated delivery of the same inbound event is recognised and not shown twice.
    const again = await simulateReply(page, "+639187654321", "Duplicate reply", "SIM-DUP-1");
    expect(again.response.status()).toBe(200);
    const duplicate = await simulateReply(page, "+639187654321", "Duplicate reply", "SIM-DUP-1");
    expect(
      ((await duplicate.response.json()) as { data: { duplicate: boolean } }).data.duplicate,
    ).toBe(true);
    await expect(thread.getByText("Duplicate reply")).toHaveCount(1);
  });

  test("a message to a number that fails is shown as failed, never delivered, and is refunded", async ({
    page,
  }) => {
    const sam = await smsUser(page, "fail");
    const balance = async () =>
      (
        await apiGet<{ data: { ledgers: { available_units: number }[] } }>(
          page.request,
          sam.user,
          "/api/v1/credits",
        )
      ).data.ledgers.reduce((n, l) => n + l.available_units, 0);
    const start = await balance();

    // +1 202 555 0101 is reserved by the simulator to fail.
    await composeSms(page, {
      countryCode: "US",
      number: "2025550101",
      body: "This one will fail",
    });
    await reviewAndSend(page);

    const thread = page.getByRole("log", { name: "SMS messages" });
    await expect(page.getByRole("group", { name: "Failure details" })).toBeVisible({
      timeout: 45_000,
    });
    await expect(thread.getByText("Delivered", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Send again" })).toBeVisible();
    await expect.poll(balance, { timeout: 30_000 }).toBe(start);
  });

  test("without the recipient's consent the message cannot be reviewed or sent", async ({
    page,
  }) => {
    await smsUser(page, "noc");
    await composeSms(page, { number: "0918 111 2222", body: "No consent yet", consent: false });
    await expect(page.getByRole("button", { name: "Review and send" })).toBeDisabled();
  });

  test("SMS is blocked until the sender has verified a mobile number", async ({ page }) => {
    await browserUser(page, "nov");
    await page.goto("/sms/new");
    await expect(page.getByText(/Verify your mobile number/).first()).toBeVisible();
    await page.getByLabel("Mobile number").fill("0918 111 3333");
    await page.getByLabel("Message").fill("Should not go");
    await expect(page.getByRole("button", { name: "Review and send" })).toBeDisabled();
  });
});
