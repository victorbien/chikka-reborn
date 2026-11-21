import type { Page } from "@playwright/test";
import { newPerson, browserUser, type Person } from "./support/people";
import { expect, test } from "./support/fixtures";

async function openChat(from: Person, with_: Person): Promise<string> {
  await from.page.goto(`/messages/new?user=${with_.user.userId}`);
  await expect(from.page).toHaveURL(/\/messages\/[0-9a-f-]{36}/);
  return /\/messages\/([0-9a-f-]{36})/.exec(from.page.url())?.[1] ?? "";
}

/** A message bubble. The conversation list also previews the last message, so scope to articles. */
function bubble(page: Page, text: string) {
  return page.getByRole("article").getByText(text, { exact: true });
}

async function send(page: Page, text: string): Promise<void> {
  await page.getByPlaceholder("Write a message").fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
}

test.describe("Chikka-to-Chikka messaging", () => {
  test("two people chat in real time and keep the same history after reload", async ({
    browser,
    page,
  }) => {
    const ana = await browserUser(page, "ana");
    const ben = await newPerson(browser, "ben");
    await ana.befriend(ben.user);

    const conversationId = await openChat(ana, ben);
    await ben.page.goto(`/messages/${conversationId}`);

    await send(ana.page, "Kumusta, Ben!");
    await expect(bubble(ana.page, "Kumusta, Ben!")).toBeVisible();
    // Ben receives it live, without reloading.
    await expect(bubble(ben.page, "Kumusta, Ben!")).toBeVisible();

    await send(ben.page, "Uy Ana! Kumusta ka?");
    await expect(bubble(ana.page, "Uy Ana! Kumusta ka?")).toBeVisible();

    await ana.page.reload();
    await ben.page.reload();
    for (const person of [ana, ben]) {
      await expect(bubble(person.page, "Kumusta, Ben!")).toBeVisible();
      await expect(bubble(person.page, "Uy Ana! Kumusta ka?")).toBeVisible();
    }
    // The people stayed on the Chikka channel: this is not an SMS thread.
    await expect(ana.page.getByText("SIMULATED")).toHaveCount(0);
  });

  test("a message that contains markup is shown as text, never run", async ({ browser, page }) => {
    const ana = await browserUser(page, "xssa");
    const ben = await newPerson(browser, "xssb");
    await ana.befriend(ben.user);
    const conversationId = await openChat(ana, ben);
    await ben.page.goto(`/messages/${conversationId}`);

    const payload = `<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>`;
    await send(ana.page, payload);
    await expect(bubble(ben.page, payload)).toBeVisible();
    expect(
      await ben.page.evaluate(() => (window as unknown as { __pwned?: number }).__pwned),
    ).toBeUndefined();
    expect(await ben.page.locator("[onerror]").count()).toBe(0);
  });

  test("people who are not contacts cannot start a conversation", async ({ browser, page }) => {
    const ana = await browserUser(page, "nca");
    const ben = await newPerson(browser, "ncb");
    const response = await ana.api.post("/api/v1/conversations", { user_id: ben.user.userId });
    expect(response.status()).toBeGreaterThanOrEqual(400);
    expect(response.status()).toBeLessThan(500);
  });

  test("an outsider cannot open someone else's conversation", async ({ browser, page }) => {
    const ana = await browserUser(page, "pra");
    const ben = await newPerson(browser, "prb");
    const eve = await newPerson(browser, "eve");
    await ana.befriend(ben.user);
    const conversationId = await openChat(ana, ben);
    await send(ana.page, "Private words");

    await eve.page.goto(`/messages/${conversationId}`);
    await expect(bubble(eve.page, "Private words")).toHaveCount(0);
    const read = await eve.api.post(`/api/v1/conversations/${conversationId}/messages`, {
      client_message_id: crypto.randomUUID(),
      body: "intruding",
    });
    expect(read.status()).toBeGreaterThanOrEqual(403);
  });
});
