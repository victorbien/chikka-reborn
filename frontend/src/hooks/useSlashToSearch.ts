import { useEffect, type RefObject } from "react";

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** Pressing "/" outside a text field focuses the first search box inside `rootRef`. */
export function useSlashToSearch(rootRef: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.altKey || event.ctrlKey || event.metaKey) return;
      if (isTyping(event.target)) return;
      const box = rootRef.current?.querySelector<HTMLInputElement>('input[type="search"]');
      if (!box) return;
      event.preventDefault();
      box.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [rootRef]);
}
