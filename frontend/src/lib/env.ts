import { z } from "zod";

/**
 * Public, build-time configuration. Only VITE_-prefixed values reach the browser,
 * so nothing secret (provider credentials, service-role keys) may ever be added here.
 */
const envSchema = z.object({
  VITE_API_BASE_URL: z.url().default("http://localhost:8000"),
  VITE_SUPABASE_URL: z.url().optional(),
  VITE_SUPABASE_ANON_KEY: z.string().min(1).optional(),
  VITE_APP_ENV: z.enum(["development", "test", "staging", "production"]).default("development"),
});

export type AppEnv = z.infer<typeof envSchema>;

/** Treat empty strings (as left in a copied .env.example) as unset. */
function withoutEmptyValues(source: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(source).filter(([, value]) => value !== ""));
}

export function parseEnv(source: Record<string, unknown>): AppEnv {
  const result = envSchema.safeParse(withoutEmptyValues(source));
  if (!result.success) {
    const problems = result.error.issues
      .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
      .join("; ");
    throw new Error(`Invalid frontend environment configuration: ${problems}`);
  }
  return result.data;
}

export const env: AppEnv = parseEnv(import.meta.env as Record<string, unknown>);
