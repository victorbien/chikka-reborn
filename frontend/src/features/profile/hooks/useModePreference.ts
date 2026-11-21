import { useCallback } from "react";
import { useUpdateProfile } from "@/features/profile/hooks/useProfile";
import { useDisplayMode, type DisplayMode } from "@/lib/display-mode";

/**
 * The Classic/Modern choice. It applies at once and is saved to the profile, so it follows the
 * user to other devices. If saving fails the previous mode comes back. Only the interface
 * changes; conversations, contacts and settings come from the same queries in both modes.
 */
export function useModePreference() {
  const { mode, setMode } = useDisplayMode();
  const { mutate, isPending, isError, error } = useUpdateProfile();

  const choose = useCallback(
    (next: DisplayMode) => {
      if (next === mode) return;
      const previous = mode;
      setMode(next);
      mutate({ ui_mode: next }, { onError: () => setMode(previous) });
    },
    [mode, mutate, setMode],
  );

  return { mode, choose, isSaving: isPending, saveFailed: isError, error };
}
