import { useSyncExternalStore } from "react";

/** Follows a CSS media query. Reports false where matchMedia does not exist (e.g. jsdom). */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      if (typeof window.matchMedia !== "function") return () => undefined;
      const list = window.matchMedia(query);
      list.addEventListener("change", notify);
      return () => list.removeEventListener("change", notify);
    },
    () => typeof window.matchMedia === "function" && window.matchMedia(query).matches,
    () => false,
  );
}

/** Tailwind's `lg` breakpoint: the three-column messenger needs this much room. */
export const DESKTOP_QUERY = "(min-width: 1024px)";
