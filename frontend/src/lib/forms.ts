import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import { isApiError } from "@/lib/api/errors";

interface Problem {
  field: string;
  reason: string;
}

function problemsOf(details: Record<string, unknown>): Problem[] {
  const raw = details.problems;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (item): item is Problem =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as Problem).field === "string" &&
      typeof (item as Problem).reason === "string",
  );
}

/**
 * Map the API's 422 field problems ("body.email") onto form fields. Returns true when at least
 * one field error was applied, so the caller can skip a generic banner.
 */
export function applyServerFieldErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): boolean {
  if (!isApiError(error) || error.status !== 422) return false;
  let applied = false;
  for (const problem of problemsOf(error.details)) {
    const name = problem.field.replace(/^body\./, "") as Path<T>;
    if (fields.includes(name)) {
      setError(name, { type: "server", message: problem.reason });
      applied = true;
    }
  }
  return applied;
}

/** A 422 with field problems is shown next to the fields, not as a banner. */
export function hasFieldProblems(error: unknown): boolean {
  return isApiError(error) && error.status === 422 && problemsOf(error.details).length > 0;
}

/** Seconds from a 429 response, for "try again in N minutes" messages. */
export function retryAfterSeconds(error: unknown): number | null {
  if (!isApiError(error) || error.status !== 429) return null;
  const value = error.details.retry_after_seconds;
  return typeof value === "number" && value > 0 ? value : null;
}

export function formatWait(seconds: number): string {
  if (seconds < 60) return `${seconds} seconds`;
  const minutes = Math.ceil(seconds / 60);
  return minutes === 1 ? "1 minute" : `${minutes} minutes`;
}
