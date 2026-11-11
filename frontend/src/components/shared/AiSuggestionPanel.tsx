import { RefreshCw, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export type AiPanelState = "loading" | "ready" | "error";

export interface AiSuggestionPanelProps {
  state: AiPanelState;
  suggestions: string[];
  /** Puts text in the composer. Never sends. */
  onUse: (suggestion: string) => void;
  onRegenerate: () => void;
  onDismiss: () => void;
  errorMessage?: string;
}

export function AiSuggestionPanel({
  state,
  suggestions,
  onUse,
  onRegenerate,
  onDismiss,
  errorMessage = "AI suggestions are unavailable right now. You can still write your message.",
}: AiSuggestionPanelProps) {
  return (
    <section aria-label="AI suggestions" className="rounded-panel border border-ai bg-surface p-3">
      <header className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles aria-hidden className="size-4 text-ai" />
          AI suggestions
        </h3>
        <Button size="icon" variant="ghost" onClick={onDismiss} aria-label="Dismiss AI suggestions">
          <X aria-hidden className="size-4" />
        </Button>
      </header>
      <p className="text-xs text-fg-muted">
        Suggestions only. Nothing is sent until you press Send.
      </p>

      <div aria-live="polite" className="mt-2">
        {state === "loading" ? <p className="text-sm text-fg-muted">Thinking…</p> : null}
        {state === "error" ? <p className="text-sm text-danger">{errorMessage}</p> : null}
        {state === "ready" ? (
          <ul className="space-y-2">
            {suggestions.map((suggestion) => (
              <li key={suggestion} className="flex items-center justify-between gap-2">
                <span className="text-sm">{suggestion}</span>
                <Button size="sm" variant="secondary" onClick={() => onUse(suggestion)}>
                  Use
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <Button
        size="sm"
        variant="ghost"
        onClick={onRegenerate}
        disabled={state === "loading"}
        className="mt-2"
      >
        <RefreshCw aria-hidden className="size-4" />
        Regenerate
      </Button>
    </section>
  );
}
