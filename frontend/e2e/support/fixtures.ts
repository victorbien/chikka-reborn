import { test as base, expect } from "@playwright/test";
import { resetRateLimits } from "./api";

/**
 * Every spec starts with empty per-IP quotas. All specs share one IP, so without this the
 * 10-per-hour sign-up limit would fail the suite for reasons unrelated to what it tests.
 *
 * Every extra browser context a spec opens (a second person, another device) is closed when the
 * spec ends. With one worker the browser lives for the whole run, so a context left open keeps a
 * signed-in SPA polling and holding a WebSocket for every later spec, which slowed the run until
 * navigations timed out.
 */
export const test = base.extend<{ freshQuotas: void; closeExtraContexts: void }>({
  freshQuotas: [
    async ({ request }, use) => {
      await resetRateLimits(request);
      await use();
    },
    { auto: true },
  ],
  closeExtraContexts: [
    async ({ browser, context }, use) => {
      await use();
      await Promise.all(
        browser
          .contexts()
          .filter((other) => other !== context)
          .map((other) => other.close()),
      );
    },
    { auto: true },
  ],
});

export { expect };
