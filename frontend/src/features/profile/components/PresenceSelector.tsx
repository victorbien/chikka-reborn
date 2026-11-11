import { PresenceIndicator } from "@/components/shared/PresenceIndicator";
import { FormAlert } from "@/components/common/FormAlert";
import { usePresence } from "@/features/profile/hooks/usePresenceHeartbeat";
import { useSetPresence } from "@/features/profile/hooks/useProfile";
import type { PresenceInfo, PresencePreference, Profile } from "@/features/profile/types";
import { toUserFacingError } from "@/lib/error-handling";
import type { PresenceStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const OPTIONS: { value: PresencePreference; label: string; description: string }[] = [
  { value: "online", label: "Online", description: "Shown as away after 5 idle minutes" },
  { value: "away", label: "Away", description: "Contacts see you are not at your screen" },
  { value: "busy", label: "Busy", description: "Contacts see you prefer not to be disturbed" },
  { value: "invisible", label: "Invisible", description: "You appear offline to everyone" },
];

/** Map to the shared indicator's states (busy shows as away; invisible as offline). */
function indicatorFor(status: PresenceInfo["status"]): PresenceStatus {
  if (status === "online") return "online";
  if (status === "away" || status === "busy") return "away";
  return "offline";
}

export function PresenceSelector({ profile }: { profile: Profile }) {
  const setPresence = useSetPresence();
  const presence = usePresence(true);
  const current = setPresence.variables ?? profile.presence_preference;

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-semibold">Your status</legend>
      {presence.data ? (
        <p className="flex items-center gap-2 text-sm" aria-live="polite">
          Others currently see:
          <PresenceIndicator status={indicatorFor(presence.data.status)} showLabel />
          {presence.data.status === "busy" ? <span>(busy)</span> : null}
        </p>
      ) : null}
      <div className="grid gap-2 sm:grid-cols-2">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className={cn(
              "flex min-h-11 cursor-pointer flex-col rounded-panel border p-2 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent",
              current === option.value
                ? "border-accent bg-surface-raised"
                : "border-border bg-surface",
            )}
          >
            <input
              type="radio"
              name="presence"
              className="sr-only"
              checked={current === option.value}
              disabled={setPresence.isPending}
              onChange={() => setPresence.mutate(option.value)}
            />
            <span className="text-sm font-medium">{option.label}</span>
            <span className="text-xs text-fg-muted">{option.description}</span>
          </label>
        ))}
      </div>
      {setPresence.error ? (
        <FormAlert tone="error">{toUserFacingError(setPresence.error).message}</FormAlert>
      ) : null}
    </fieldset>
  );
}
