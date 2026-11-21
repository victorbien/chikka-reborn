import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactElement, ReactNode } from "react";

export interface TipProps {
  /** Short text shown on hover and keyboard focus. */
  label: ReactNode;
  /** One focusable element. The tooltip never replaces its accessible name. */
  children: ReactElement;
  side?: "top" | "right" | "bottom" | "left";
}

/** A tooltip around one element. It brings its own provider so it works anywhere. */
export function Tip({ label, children, side = "bottom" }: TipProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={400} skipDelayDuration={200}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={6}
            className="z-50 max-w-60 rounded-control border border-border bg-surface-raised px-2 py-1 text-xs text-fg bevel motion-safe:animate-[chikka-fade-in_120ms_ease-out]"
          >
            {label}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
