import { useDisplayMode, type DisplayMode } from "@/lib/display-mode";
import { cn } from "@/lib/utils";

const OPTIONS: { value: DisplayMode; label: string; description: string }[] = [
  { value: "modern", label: "Modern", description: "Roomy layout with AI panel" },
  { value: "classic", label: "Classic", description: "Compact buddy-list style" },
];

/** Persisted via DisplayModeProvider (localStorage). */
export function ModeSwitcher() {
  const { mode, setMode } = useDisplayMode();
  return (
    <fieldset className="flex gap-2">
      <legend className="mb-1 text-sm font-semibold">Display mode</legend>
      {OPTIONS.map((option) => (
        <label
          key={option.value}
          className={cn(
            "flex min-h-11 flex-1 cursor-pointer flex-col rounded-panel border p-2 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent",
            mode === option.value ? "border-accent bg-surface-raised" : "border-border bg-surface",
          )}
        >
          <input
            type="radio"
            name="display-mode"
            className="sr-only"
            checked={mode === option.value}
            onChange={() => setMode(option.value)}
          />
          <span className="text-sm font-medium">{option.label}</span>
          <span className="text-xs text-fg-muted">{option.description}</span>
        </label>
      ))}
    </fieldset>
  );
}
