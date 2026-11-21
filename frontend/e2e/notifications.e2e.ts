import { browserUser, newPerson } from "./support/people";
import { expect, test } from "./support/fixtures";

test.describe("notifications", () => {
  test("a new message raises an unread notification that can be read and dismissed", async ({
    browser,
    page,
  }) => {
    const ana = await browserUser(page, "nta");
    const ben = await newPerson(browser, "ntb");
    await ana.befriend(ben.user);
    const opened = await ben.api.post("/api/v1/conversations", { user_id: ana.user.userId });
    const conversationId = ((await opened.json()) as { data: { id: string } }).data.id;

    await expect(page.getByRole("link", { name: /^Notifications/ })).toBeVisible();
    await ben.api.post(`/api/v1/conversations/${conversationId}/messages`, {
      client_message_id: crypto.randomUUID(),
      body: "A secret body that must not be echoed",
    });

    // The bell updates live, then the page lists the notification.
    await expect(page.getByRole("link", { name: /Notifications, \d+ unread/ })).toBeVisible({
      timeout: 20_000,
    });
    await page.getByRole("link", { name: /Notifications/ }).click();
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    const list = page.getByRole("list", { name: "Notifications" });
    await expect(list.getByRole("listitem").first()).toBeVisible();
    // Notifications carry no message text.
    await expect(page.getByText("A secret body that must not be echoed")).toHaveCount(0);

    await page.getByRole("button", { name: "Mark all as read" }).click();
    await expect(page.getByText("You are all caught up.")).toBeVisible();
    await expect(page.getByRole("link", { name: /^Notifications$/ })).toBeVisible();

    // Dismiss everything (the new message and the accepted contact request).
    const dismiss = list.getByRole("button", { name: /^Dismiss:/ });
    while ((await dismiss.count()) > 0) {
      const before = await dismiss.count();
      await dismiss.first().click();
      await expect(dismiss).toHaveCount(before - 1);
    }
    await expect(page.getByText("No notifications yet")).toBeVisible();
  });

  test("shows an empty state for a new person and a working settings page", async ({ page }) => {
    await browserUser(page, "emp");
    await page.goto("/notifications");
    await expect(page.getByText("No notifications yet")).toBeVisible();
    await page.getByRole("main").getByRole("link", { name: "Settings" }).click();
    await expect(page).toHaveURL(/\/settings\/notifications/);
  });
});
