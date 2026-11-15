import { useCallback, type KeyboardEvent } from "react";

/**
 * Up/Down/Home/End move focus between the items of a list, so a long list is one Tab stop
 * to reach and one key press to move through. Items are found with `itemSelector`.
 */
export function useArrowKeyNavigation(itemSelector: string) {
  return useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const keys = ["ArrowDown", "ArrowUp", "Home", "End"];
      if (!keys.includes(event.key)) return;
      const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(itemSelector));
      const enabled = items.filter((item) => !item.hasAttribute("disabled"));
      if (enabled.length === 0) return;
      const current = enabled.indexOf(document.activeElement as HTMLElement);
      let next: number;
      if (event.key === "Home") next = 0;
      else if (event.key === "End") next = enabled.length - 1;
      else if (event.key === "ArrowDown") next = Math.min(enabled.length - 1, current + 1);
      else next = Math.max(0, current === -1 ? 0 : current - 1);
      event.preventDefault();
      enabled[next]?.focus();
    },
    [itemSelector],
  );
}
