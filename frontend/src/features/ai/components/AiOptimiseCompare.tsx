import type { OptimiseSmsResult, SegmentCount } from "@/features/ai/types";

function describe(count: SegmentCount): string {
  const encoding = count.encoding === "gsm7" ? "GSM-7" : "Unicode";
  const segments = count.segments === 1 ? "1 segment" : `${count.segments} segments`;
  return `${count.characters} characters, ${encoding}, ${segments}`;
}

/** Original and optimised side by side. Counts are estimates: the carrier decides the split,
 *  and no price is claimed here. */
export function AiOptimiseCompare({ result }: { result: OptimiseSmsResult }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <section aria-label="Original message" className="rounded-control border border-border p-2">
        <h4 className="text-xs font-semibold">Original</h4>
        <p className="text-xs text-fg-muted">{describe(result.original)}</p>
        <p className="mt-1 whitespace-pre-wrap text-sm">{result.original_text}</p>
      </section>
      <section aria-label="Shorter version" className="rounded-control border border-ai p-2">
        <h4 className="text-xs font-semibold">Shorter version</h4>
        {result.optimised && result.optimised_text ? (
          <>
            <p className="text-xs text-fg-muted">{describe(result.optimised)}</p>
            <p className="mt-1 whitespace-pre-wrap text-sm">{result.optimised_text}</p>
          </>
        ) : (
          <p className="mt-1 text-sm text-fg-muted">No shorter version.</p>
        )}
      </section>
      {result.optimised_text ? (
        <p className="text-xs text-fg-muted sm:col-span-2">
          {result.within_target
            ? `Fits in ${result.max_segments} segment${result.max_segments === 1 ? "" : "s"}.`
            : `Shorter, but still more than ${result.max_segments} segment${result.max_segments === 1 ? "" : "s"}.`}{" "}
          Read it carefully: the AI may have changed the meaning. Segment counts are estimates.
        </p>
      ) : null}
    </div>
  );
}
