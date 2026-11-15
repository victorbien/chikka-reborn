import { MonitorSmartphone, Sparkles } from "lucide-react";
import { FormAlert } from "@/components/common/FormAlert";
import { ModeSwitcher } from "@/components/shared/ModeSwitcher";
import { Button } from "@/components/ui/button";
import { Tip } from "@/components/ui/tooltip";
import { useModePreference } from "@/features/profile/hooks/useModePreference";

/** Header button that flips between Modern and Classic. */
export function ModeToggle() {
  const { mode, choose, isSaving, saveFailed } = useModePreference();
  const target = mode === "modern" ? "classic" : "modern";
  const targetLabel = target === "classic" ? "Classic" : "Modern";
  return (
    <>
      <Tip label={`Switch to ${targetLabel} mode`}>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Switch to ${targetLabel} mode`}
          disabled={isSaving}
          onClick={() => choose(target)}
        >
          {mode === "modern" ? (
            <MonitorSmartphone aria-hidden className="size-4" />
          ) : (
            <Sparkles aria-hidden className="size-4" />
          )}
        </Button>
      </Tip>
      <span role="status" className="sr-only">
        {saveFailed ? "Your interface choice could not be saved." : ""}
      </span>
    </>
  );
}

/** Settings version: both options with descriptions, saved to the profile. */
export function PersistedModeSwitcher() {
  const { choose, isSaving, saveFailed } = useModePreference();
  return (
    <div className="space-y-2">
      <ModeSwitcher onChange={choose} disabled={isSaving} />
      {saveFailed ? (
        <FormAlert tone="error">
          Your interface choice could not be saved, so the previous one is back. Try again.
        </FormAlert>
      ) : null}
    </div>
  );
}
