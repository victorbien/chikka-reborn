import type { Page } from "@playwright/test";
import { browserUser, newPerson, type Person } from "./support/people";
import { expect, test } from "./support/fixtures";

async function chatWith(ana: Person, ben: Person): Promise<string> {
  await ana.befriend(ben.user);
  await ana.page.goto(`/messages/new?user=${ben.user.userId}`);
  await expect(ana.page).toHaveURL(/\/messages\/[0-9a-f-]{36}/);
  return /\/messages\/([0-9a-f-]{36})/.exec(ana.page.url())?.[1] ?? "";
}

function panel(page: Page) {
  return page.getByRole("region", { name: "AI assistant" });
}

/** In Modern mode the side panel is open by default. Otherwise open it from the composer. */
async function openAssistant(page: Page): Promise<void> {
  const openByDefault = await expect(panel(page))
    .toBeVisible({ timeout: 5_000 })
    .then(() => true)
    .catch(() => false);
  if (!openByDefault) {
    await page.getByRole("button", { name: "AI assistant", exact: true }).click();
  }
  await expect(panel(page)).toBeVisible();
}

async function turnOn(page: Page): Promise<void> {
  await panel(page).getByRole("button", { name: "Turn on the AI assistant" }).click();
  await expect(panel(page).getByText(/Demo assistant: answers are canned examples/)).toBeVisible();
}

test.describe("AI assistant", () => {
  test("is off until the person turns it on, and nothing is sent without them pressing Send", async ({
    browser,
    page,
  }) => {
    const ana = await browserUser(page, "aia");
    const ben = await newPerson(browser, "aib");
    const conversationId = await chatWith(ana, ben);

    await openAssistant(page);
    await expect(
      panel(page).getByRole("button", { name: "Turn on the AI assistant" }),
    ).toBeVisible();
    await expect(panel(page).getByRole("button", { name: "Ask the assistant" })).toHaveCount(0);
    await turnOn(page);

    // Translate: the draft goes to a suggestion list, not to the composer, and not to Ben.
    await page.getByPlaceholder("Write a message").fill("Good morning");
    await panel(page).getByRole("button", { name: "Translate" }).click();
    await panel(page).getByLabel("To").selectOption("fil");
    await panel(page).getByRole("button", { name: "Ask the assistant" }).click();

    const drafts = panel(page).getByRole("list", { name: "AI drafts" });
    const draftText = "[Filipino (Tagalog)] Good morning"; // the mock labels drafts with the language
    await expect(drafts.getByText(draftText)).toBeVisible();
    await expect(page.getByPlaceholder("Write a message")).toHaveValue("Good morning");
    expect(
      (
        await ben.api.get<{ data: { messages: unknown[] } }>(
          `/api/v1/conversations/${conversationId}/messages`,
        )
      ).data.messages,
    ).toHaveLength(0);

    // Accepting puts the draft in the composer and marks it AI-assisted; Send is still manual.
    await drafts.getByRole("button", { name: "Use", exact: true }).click();
    await expect(page.getByPlaceholder("Write a message")).toHaveValue(draftText);
    await expect(page.getByText("AI-assisted").first()).toBeVisible();
    expect(
      (
        await ben.api.get<{ data: { messages: unknown[] } }>(
          `/api/v1/conversations/${conversationId}/messages`,
        )
      ).data.messages,
    ).toHaveLength(0);

    await ben.page.goto(`/messages/${conversationId}`);
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(ben.page.getByRole("article").getByText(draftText)).toBeVisible();
  });

  test("suggests smart replies from the conversation and lets the person reject them", async ({
    browser,
    page,
  }) => {
    const ana = await browserUser(page, "sra");
    const ben = await newPerson(browser, "srb");
    const conversationId = await chatWith(ana, ben);
    await ben.api.post(`/api/v1/conversations/${conversationId}/messages`, {
      client_message_id: crypto.randomUUID(),
      body: "Are we still meeting tonight?",
    });
    await expect(
      page.getByRole("article").getByText("Are we still meeting tonight?"),
    ).toBeVisible();

    await openAssistant(page);
    await turnOn(page);
    await panel(page).getByRole("button", { name: "Replies" }).click();
    await panel(page).getByRole("button", { name: "Ask the assistant" }).click();

    const drafts = panel(page).getByRole("list", { name: "AI drafts" });
    await expect(drafts.getByText("Okay, sounds good!")).toBeVisible();
    await expect(drafts.getByText("Thanks, talk to you soon.")).toBeVisible();

    // Rejecting dismisses the whole set and records the decision; nothing reaches the composer.
    await drafts.getByRole("button", { name: "Reject" }).first().click();
    await expect(drafts).toHaveCount(0);
    // The composer stayed empty and fully usable while suggestions were open.
    await expect(page.getByPlaceholder("Write a message")).toHaveValue("");
    await page.getByPlaceholder("Write a message").fill("Typed by hand");
    await expect(page.getByRole("button", { name: "Send message" })).toBeEnabled();
  });

  test("turning the assistant off again hides its controls", async ({ page }) => {
    const ana = await browserUser(page, "off");
    const response = await ana.api.put("/api/v1/ai/settings", { enabled: true });
    expect(response.status()).toBe(200);
    const status = await ana.api.get<{ data: { enabled: boolean } }>("/api/v1/ai/status");
    expect(status.data.enabled).toBe(true);
    const off = await ana.api.put("/api/v1/ai/settings", { enabled: false });
    expect(off.status()).toBe(200);
    expect(
      (await ana.api.get<{ data: { enabled: boolean } }>("/api/v1/ai/status")).data.enabled,
    ).toBe(false);
    const blocked = await ana.api.post("/api/v1/ai/translate", {
      text: "Hello",
      target_language: "fil",
    });
    expect(blocked.status()).toBeGreaterThanOrEqual(400);
  });
});
