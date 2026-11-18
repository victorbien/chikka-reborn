import { browserUser, newPerson } from "./support/people";
import { expect, test } from "./support/fixtures";

test.describe("contact management", () => {
  test("finds a person by username, sends a request, and they accept it", async ({
    browser,
    page,
  }) => {
    const ana = await browserUser(page, "ana");
    const ben = await newPerson(browser, "ben");

    await ana.page.goto("/contacts");
    await expect(ana.page.getByRole("heading", { name: "Contacts" })).toBeVisible();
    await expect(ana.page.getByText("No contacts yet")).toBeVisible();

    await ana.page.getByRole("button", { name: "Add contact" }).click();
    const dialog = ana.page.getByRole("dialog", { name: "Add a contact" });
    await dialog.getByLabel("Username, email or mobile number").fill(ben.user.username);
    await dialog.getByRole("button", { name: `Add ${ben.user.displayName}` }).click();
    await expect(dialog.getByText("Request sent")).toBeVisible();
    await ana.page.keyboard.press("Escape");

    // Ben sees the request and accepts it.
    await ben.page.goto("/contacts");
    await ben.page.getByRole("button", { name: /^Requests/ }).click();
    await ben.page
      .getByRole("button", { name: `Accept request from ${ana.user.displayName}` })
      .click();

    // Both lists now hold each other.
    await ben.page.getByRole("button", { name: "Contacts", exact: true }).click();
    await expect(
      ben.page.getByRole("list", { name: "Contacts" }).getByText(ana.user.displayName),
    ).toBeVisible();
    await ana.page.reload();
    await expect(
      ana.page.getByRole("list", { name: "Contacts" }).getByText(ben.user.displayName),
    ).toBeVisible();
  });

  test("an unknown username finds nobody and says so", async ({ page }) => {
    const ana = await browserUser(page, "lone");
    await ana.page.goto("/contacts");
    await ana.page.getByRole("button", { name: "Add contact" }).click();
    await ana.page
      .getByRole("dialog", { name: "Add a contact" })
      .getByLabel("Username, email or mobile number")
      .fill("nobody_here_zz");
    await expect(
      ana.page.getByText("No one found. Check the spelling, or ask them for their username."),
    ).toBeVisible();
  });

  test("rejecting a request leaves no contact, and removing a contact asks for confirmation", async ({
    browser,
    page,
  }) => {
    const ana = await browserUser(page, "rej");
    const ben = await newPerson(browser, "rjb");
    const cat = await newPerson(browser, "cat");

    // Ana asks Ben; Ben rejects.
    const found = await ana.api.get<{ data: { people: { user_id: string }[] } }>(
      "/api/v1/contacts/search",
      { q: ben.user.username },
    );
    await ana.api.post("/api/v1/contacts/requests", {
      user_id: found.data.people[0]?.user_id,
      note: null,
    });
    await ben.page.goto("/contacts");
    await ben.page.getByRole("button", { name: /^Requests/ }).click();
    await ben.page
      .getByRole("button", { name: `Reject request from ${ana.user.displayName}` })
      .click();
    await ana.page.goto("/contacts");
    await expect(ana.page.getByText("No contacts yet")).toBeVisible();

    // Ana befriends Cat through the API, then removes her in the UI.
    await ana.befriend(cat.user);
    await ana.page.reload();
    await ana.page.getByRole("list", { name: "Contacts" }).getByText(cat.user.displayName).click();
    await ana.page.getByRole("button", { name: "Remove contact" }).click();
    await ana.page
      .getByRole("dialog", { name: `Remove ${cat.user.displayName}?` })
      .getByRole("button", { name: "Remove" })
      .click();
    await expect(ana.page.getByText("No contacts yet")).toBeVisible();
  });
});
