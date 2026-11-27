import { useState } from "react";
import { cn } from "@/lib/utils";

/** Fixed order, so the ghost is predictable and testable. */
export const GHOST_QUIPS = [
  "Boo! Just kidding. I only haunt group chats.",
  "I was offline for years. Seen at 2018, replying now.",
  "No, I cannot see your messages. I can only judge your typing speed.",
  "Poking a ghost is free. Texting is not, so check the cost first.",
  "Still here. Still translucent. Still faster than a letter.",
] as const;

/**
 * A friendly ghost. Poking it shows the next quip. The quip is announced to
 * screen readers through a polite live region.
 */
export function GhostMascot({ className }: { className?: string }) {
  const [quipIndex, setQuipIndex] = useState(0);
  const [pokes, setPokes] = useState(0);
  const quip = GHOST_QUIPS[quipIndex % GHOST_QUIPS.length];

  function poke(): void {
    setPokes((count) => count + 1);
    setQuipIndex((index) => (index + 1) % GHOST_QUIPS.length);
  }

  return (
    <div className={cn("flex flex-col items-center gap-3", className)}>
      <p
        aria-live="polite"
        className="min-h-14 max-w-xs rounded-panel border border-border bg-surface-raised px-3 py-2 text-center text-sm bevel"
      >
        {pokes === 0 ? "Psst. Poke me." : quip}
      </p>
      <button
        type="button"
        onClick={poke}
        aria-label="Poke the ghost"
        className="rounded-full p-2 transition-transform hover:scale-105 active:scale-95"
      >
        <svg
          viewBox="0 0 120 140"
          role="img"
          aria-hidden="true"
          className="h-36 w-auto motion-safe:animate-[chikka-float_4s_ease-in-out_infinite]"
        >
          <path
            d="M60 8C33 8 14 29 14 56v66c0 6 6 9 11 5l11-9 12 10c3 3 8 3 11 0l11-10 11 10c3 3 8 3 11 0l12-10 11 9c5 4 11 1 11-5V56C106 29 87 8 60 8Z"
            fill="var(--fg)"
          />
          <ellipse cx="44" cy="58" rx="7" ry="10" fill="var(--canvas)" />
          <ellipse cx="76" cy="58" rx="7" ry="10" fill="var(--canvas)" />
          <circle cx="46" cy="55" r="2.5" fill="var(--fg)" />
          <circle cx="78" cy="55" r="2.5" fill="var(--fg)" />
          <ellipse cx="32" cy="76" rx="7" ry="4" fill="var(--accent)" opacity="0.45" />
          <ellipse cx="88" cy="76" rx="7" ry="4" fill="var(--accent)" opacity="0.45" />
          <path
            d="M50 82c4 7 16 7 20 0"
            fill="none"
            stroke="var(--canvas)"
            strokeWidth="4"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </div>
  );
}
