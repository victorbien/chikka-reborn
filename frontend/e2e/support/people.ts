import type { APIResponse, Browser, Page } from "@playwright/test";
import { expect } from "@playwright/test";
import { apiGet, apiPost, apiPut, befriend, createUser, verifyPhone, type TestUser } from "./api";

export interface Person {
  user: TestUser;
  page: Page;
  api: {
    get: <T>(path: string, params?: Record<string, string>) => Promise<T>;
    post: (path: string, data: unknown, headers?: Record<string, string>) => Promise<APIResponse>;
    put: (path: string, data: unknown) => Promise<APIResponse>;
  };
  befriend: (other: TestUser) => Promise<void>;
  verifyPhone: (mobile?: string) => Promise<string>;
}

function wrap(page: Page, user: TestUser): Person {
  const request = page.request;
  return {
    user,
    page,
    api: {
      get: (path, params) => apiGet(request, user, path, params),
      post: (path, data, headers) => apiPost(request, user, path, data, headers),
      put: (path, data) => apiPut(request, user, path, data),
    },
    befriend: (other) => befriend(request, user, other),
    verifyPhone: (mobile) => verifyPhone(request, user, mobile),
  };
}

/**
 * Creates a user on the test's own page and opens the app signed in. The refresh cookie is set
 * in this page's context by the verification call, so the SPA restores the session on load.
 */
export async function browserUser(
  page: Page,
  label: string,
  options: { uiMode?: "modern" | "classic" } = {},
): Promise<Person> {
  const user = await createUser(page.request, label, options);
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  return wrap(page, user);
}

/** Another person in a separate browser context (own cookies, own session), signed in. */
export async function newPerson(
  browser: Browser,
  label: string,
  options: { uiMode?: "modern" | "classic" } = {},
): Promise<Person> {
  const context = await browser.newContext({ baseURL: "http://localhost:5173" });
  const page = await context.newPage();
  return browserUser(page, label, options);
}
