import { apiGet, createUser, signInBrowser, type TestUser } from "./support/api";
import { expect, test } from "./support/fixtures";

// 1x1 transparent PNG: a valid image under the 2 MB limit.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

async function openProfile(page: import("@playwright/test").Page, user: TestUser) {
  await signInBrowser(page, user, "/settings/profile");
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
}

test.describe("profile management", () => {
  test("edits the display name and bio, and the change persists after a reload", async ({
    page,
  }) => {
    const user = await createUser(page.request, "prof");
    await openProfile(page, user);

    const form = page.getByRole("form", { name: "Profile details" });
    await expect(form.getByLabel("Username")).toBeDisabled();
    await expect(form.getByLabel("Email")).toBeDisabled();
    await expect(form.getByRole("button", { name: "Save changes" })).toBeDisabled();

    await form.getByLabel("Display name").fill("Renamed Person");
    await form.getByLabel("Bio").fill("Hello from the browser suite");
    await form.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByText("Profile saved.")).toBeVisible();

    await page.reload();
    await expect(
      page.getByRole("form", { name: "Profile details" }).getByLabel("Display name"),
    ).toHaveValue("Renamed Person");
    const me = await apiGet<{ data: { display_name: string; bio: string } }>(
      page.request,
      user,
      "/api/v1/users/me",
    );
    expect(me.data).toMatchObject({
      display_name: "Renamed Person",
      bio: "Hello from the browser suite",
    });
  });

  test("rejects an over-long display name without saving", async ({ page }) => {
    const user = await createUser(page.request, "long");
    await openProfile(page, user);
    const form = page.getByRole("form", { name: "Profile details" });
    await form.getByLabel("Display name").fill("x".repeat(200));
    await form.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByText("Profile saved.")).toHaveCount(0);
    const me = await apiGet<{ data: { display_name: string } }>(
      page.request,
      user,
      "/api/v1/users/me",
    );
    expect(me.data.display_name).toBe(user.displayName);
  });

  test("uploads a profile photo and refuses a file type that is not an image", async ({ page }) => {
    const user = await createUser(page.request, "photo");
    await openProfile(page, user);
    const chooser = page.getByLabel("Choose a profile photo");

    await chooser.setInputFiles({
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("hi"),
    });
    await expect(page.getByText("Use a JPEG, PNG or WebP image.")).toBeVisible();

    await chooser.setInputFiles({ name: "me.png", mimeType: "image/png", buffer: PNG });
    await expect(page.getByText("Photo updated.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove" })).toBeVisible();
  });

  test("verifies a mobile number from the simulated inbox", async ({ page }) => {
    const user = await createUser(page.request, "phone");
    await openProfile(page, user);
    const mobile = "+639171230001";

    await page
      .getByRole("form", { name: "Add a mobile number" })
      .getByLabel("Mobile number")
      .fill(mobile);
    await page.getByRole("button", { name: "Send code" }).click();

    // Simulation: the code is shown in the page, never sent to a real handset.
    await expect(page.getByRole("heading", { name: "Simulated SMS inbox" })).toBeVisible();
    await expect(page.getByText("SIMULATED").first()).toBeVisible();
    const inbox = await apiGet<{ data: { body: string }[] }>(
      page.request,
      user,
      "/api/v1/users/me/phone/simulated-inbox",
    );
    const code = /\b(\d{6})\b/.exec(inbox.data[0]?.body ?? "")?.[1];
    expect(code).toBeDefined();
    await page.getByRole("textbox", { name: "Verification code" }).fill(code ?? "");
    await page.getByRole("button", { name: "Verify number" }).click();

    await expect
      .poll(async () => {
        const status = await apiGet<{ data: { verified: boolean } }>(
          page.request,
          user,
          "/api/v1/users/me/phone",
        );
        return status.data.verified;
      })
      .toBe(true);
  });
});
