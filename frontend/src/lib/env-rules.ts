/**
 * Rules for hosted builds, shared by the runtime parser (env.ts) and the build (vite.config.ts)
 * so a bad deployment fails at build time instead of showing a broken page.
 * Pure on purpose: no import.meta.env, so Node can load it.
 */
const HOSTED_ENVIRONMENTS = new Set(["staging", "production"]);
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "0.0.0.0"]);

export function hostedEnvProblem(source: {
  VITE_APP_ENV?: string;
  VITE_API_BASE_URL?: string;
}): string | null {
  if (!source.VITE_APP_ENV || !HOSTED_ENVIRONMENTS.has(source.VITE_APP_ENV)) return null;
  const raw = source.VITE_API_BASE_URL;
  if (!raw) {
    return `VITE_API_BASE_URL must be set when VITE_APP_ENV is ${source.VITE_APP_ENV}`;
  }
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return "VITE_API_BASE_URL is not a valid URL";
  }
  if (url.protocol !== "https:") {
    return "VITE_API_BASE_URL must use https in a hosted build";
  }
  if (LOCAL_HOSTS.has(url.hostname)) {
    return "VITE_API_BASE_URL must not point at a local host in a hosted build";
  }
  return null;
}
