import { browserUser } from "./support/people";
import { expect, test } from "./support/fixtures";

test.describe("Classic and Modern mode", () => {
  test("switches between Modern and Classic, keeps the choice after reload and saves it", async ({
    page,
  }) => {
    const user = await browserUser(page, "mode");
    await expect(page.locator("html")).toHaveAttribute("data-mode", "modern");

    await page.getByRole("button", { name: "Switch to Classic mode" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-mode", "classic");
    await expect(page.getByText("Chikka Reborn · Classic")).toBeVisible();
    await expect(page.getByRole("button", { name: "Switch to Modern mode" })).toBeVisible();

    // The preference is saved to the profile, so it survives a reload and a new device.
    await expect
      .poll(
        async () =>
          (await user.api.get<{ data: { ui_mode: string } }>("/api/v1/users/me")).data.ui_mode,
      )
      .toBe("classic");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-mode", "classic");

    // The Classic messenger is a buddy list that offers the same features.
    await page.goto("/messages");
    await expect(page.getByRole("heading", { name: "Messages" })).toBeAttached();
    await expect(page.getByRole("searchbox", { name: "Search buddies" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Add buddies" })).toBeVisible();

    await page.getByRole("button", { name: "Switch to Modern mode" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-mode", "modern");
  });

  test("can be chosen from the settings page", async ({ page }) => {
    await browserUser(page, "pick");
    await page.goto("/settings/profile");
    // The radios are visually hidden behind a styled label, so click the input directly.
    await page.getByRole("radio", { name: /^Classic/ }).check({ force: true });
    await expect(page.locator("html")).toHaveAttribute("data-mode", "classic");
    await page.getByRole("radio", { name: /^Modern/ }).check({ force: true });
    await expect(page.locator("html")).toHaveAttribute("data-mode", "modern");
  });

  test("a person who saved Classic gets Classic on a fresh sign-in", async ({ page }) => {
    await browserUser(page, "cls", { uiMode: "classic" });
    await expect(page.locator("html")).toHaveAttribute("data-mode", "classic");
  });
});
