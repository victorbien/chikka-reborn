import { createUser, promoteToAdmin, signInBrowser } from "./support/api";
import { browserUser } from "./support/people";
import { expect, test } from "./support/fixtures";

test.describe("administrator dashboard", () => {
  test("an administrator sees the overview, users and SMS administration", async ({ page }) => {
    const admin = await createUser(page.request, "root");
    await promoteToAdmin(page.request, admin);
    await signInBrowser(page, admin, "/admin");

    await expect(page.getByRole("heading", { name: "Administration" })).toBeVisible();
    const tabs = page.getByRole("navigation", { name: "Administration" });
    for (const name of [
      "Overview",
      "Users",
      "SMS messages",
      "AI usage",
      "Audit log",
      "SMS settings",
    ]) {
      await expect(tabs.getByRole("link", { name })).toBeVisible();
    }
    await expect(page.getByRole("heading", { name: "SMS", exact: true })).toBeVisible();
    // Simulated traffic is shown separately from live traffic.
    await expect(page.getByText("SIMULATED").first()).toBeVisible();

    await tabs.getByRole("link", { name: "Users" }).click();
    await expect(page.getByRole("heading", { name: "Accounts" })).toBeVisible();
    await expect(page.getByText(admin.displayName).first()).toBeVisible();

    await tabs.getByRole("link", { name: "Audit log" }).click();
    await expect(page).toHaveURL(/\/admin\/audit/);
    await tabs.getByRole("link", { name: "SMS settings" }).click();
    await expect(page.getByRole("heading", { name: "SMS administration" })).toBeVisible();
  });

  test("an ordinary user cannot open the admin area and the API refuses them", async ({ page }) => {
    const user = await browserUser(page, "plain");
    await expect(
      page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Admin" }),
    ).toHaveCount(0);

    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Administration" })).toHaveCount(0);

    const dashboard = await user.api
      .get<never>("/api/v1/admin/dashboard")
      .catch((error: unknown) => error);
    expect(dashboard).toBeInstanceOf(Error);
    const direct = await page.request.get("http://localhost:8010/api/v1/admin/dashboard", {
      headers: { Authorization: `Bearer ${user.user.accessToken}` },
    });
    expect(direct.status()).toBe(403);
  });
});
