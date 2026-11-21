import { PASSWORD } from "./support/stack";
import { createUser, emailToken, uniqueName } from "./support/api";
import { expect, test } from "./support/fixtures";

test.describe("registration and login", () => {
  test("a new person registers, confirms their email, sets up a profile and signs in again", async ({
    page,
    request,
  }) => {
    const username = uniqueName("reg");
    const email = `${username}@example.com`;

    await page.goto("/auth/register");
    await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Display name").fill("Reg Tester");
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByLabel(/I accept the Terms/).check();
    await page.getByRole("button", { name: "Create account" }).click();

    // The same neutral screen is shown whether or not the address was new.
    await expect(page.getByRole("heading", { name: "Confirm your email" })).toBeVisible();

    // Cannot sign in before confirming.
    await page.goto("/auth/sign-in");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Confirm your email address first.")).toBeVisible();

    // Following the emailed link signs the person in and starts onboarding.
    const token = await emailToken(request, email);
    await page.goto(`/auth/verify-email?token_hash=${token}`);
    await expect(page.getByRole("heading", { name: "Set up your profile" })).toBeVisible();
    await page.getByLabel("Username").fill(username);
    await page.getByRole("button", { name: "Finish setup" }).click();
    await expect(page.getByRole("heading", { name: "Chikka Reborn" }).first()).toBeVisible();

    // The access token lives in memory only: a reload restores the session from the cookie.
    await page.reload();
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
    expect(await page.evaluate(() => window.localStorage.length)).toBeLessThanOrEqual(1);
    const stored = await page.evaluate(() => JSON.stringify({ ...window.localStorage }));
    expect(stored).not.toMatch(/eyJ[A-Za-z0-9_-]{10,}/);
    expect(await page.evaluate(() => document.cookie)).not.toContain("chikka_refresh");

    // Sign out, then sign back in with the password.
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/auth\/sign-in/);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  });

  test("wrong credentials show one generic message and keep the person signed out", async ({
    page,
    request,
  }) => {
    const user = await createUser(request, "wrong");
    await page.goto("/auth/sign-in");
    await page.getByLabel("Email").fill(user.email);
    await page.getByLabel("Password").fill("Not-The-Password-1");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Email or password is incorrect.")).toBeVisible();
    await expect(page).toHaveURL(/\/auth\/sign-in/);

    // An address that does not exist gets exactly the same message.
    await page.getByLabel("Email").fill(`nobody-${uniqueName("x")}@example.com`);
    await page.getByLabel("Password").fill("Not-The-Password-1");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Email or password is incorrect.")).toBeVisible();
  });

  test("registration form rejects a weak password and a missing consent before sending", async ({
    page,
  }) => {
    await page.goto("/auth/register");
    await page.getByLabel("Email").fill("someone@example.com");
    await page.getByLabel("Display name").fill("Someone");
    await page.getByLabel("Password").fill("short");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/auth\/register/);
    await expect(page.getByRole("heading", { name: "Confirm your email" })).toHaveCount(0);
  });

  test("a returning person with a valid session is taken past the sign-in page", async ({
    page,
  }) => {
    await createUser(page.request, "back");
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
    await page.goto("/auth/sign-in");
    await expect(page).not.toHaveURL(/\/auth\/sign-in/);
  });
});
