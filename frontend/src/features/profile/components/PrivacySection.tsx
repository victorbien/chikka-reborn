import { FormAlert } from "@/components/common/FormAlert";
import { Select } from "@/components/ui/input";
import { usePrivacy, useUpdatePrivacy } from "@/features/profile/hooks/useProfile";
import type { PrivacySettings, ProfileVisibility, SharePresence } from "@/features/profile/types";
import { toUserFacingError } from "@/lib/error-handling";

const VISIBILITY: { value: ProfileVisibility; label: string }[] = [
  { value: "contacts", label: "Contacts can find and see my profile" },
  { value: "everyone", label: "Anyone who knows my username can find me" },
  { value: "private", label: "Nobody can find me" },
];

const PRESENCE: { value: SharePresence; label: string }[] = [
  { value: "contacts", label: "My contacts" },
  { value: "everyone", label: "Everyone" },
  { value: "nobody", label: "Nobody" },
];

function Toggle({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  disabled: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex min-h-11 items-start gap-3">
      <input
        type="checkbox"
        className="mt-1 size-5"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-fg-muted">{hint}</span>
      </span>
    </label>
  );
}

/** Who can find you and see your presence. Defaults are the most private choices. */
export function PrivacySection() {
  const privacy = usePrivacy();
  const update = useUpdatePrivacy();

  if (privacy.isPending) return <p role="status">Loading privacy settings…</p>;
  if (privacy.isError) {
    return <FormAlert tone="error">{toUserFacingError(privacy.error).message}</FormAlert>;
  }
  const settings = privacy.data;
  const change = (changes: Partial<PrivacySettings>) => update.mutate(changes);

  return (
    <div className="space-y-4">
      {update.error ? (
        <FormAlert tone="error">{toUserFacingError(update.error).message}</FormAlert>
      ) : null}
      <label className="flex flex-col gap-1 text-sm font-medium">
        Who can find me by username
        <Select
          value={settings.profile_visibility}
          disabled={update.isPending}
          onChange={(event) =>
            change({ profile_visibility: event.target.value as ProfileVisibility })
          }
        >
          {VISIBILITY.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium">
        Who can see when I am online
        <Select
          value={settings.share_presence}
          disabled={update.isPending}
          onChange={(event) => change({ share_presence: event.target.value as SharePresence })}
        >
          {PRESENCE.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </label>
      <Toggle
        label="Show my last seen time to contacts"
        hint="Off by default."
        checked={settings.show_last_seen}
        disabled={update.isPending}
        onChange={(value) => change({ show_last_seen: value })}
      />
      <Toggle
        label="Let people find me by my email address"
        hint="Only an exact match works. Nobody can tell whether an address is registered."
        checked={settings.discoverable_by_email}
        disabled={update.isPending}
        onChange={(value) => change({ discoverable_by_email: value })}
      />
      <Toggle
        label="Let people find me by my mobile number"
        hint="Needs a verified number. Only an exact match works."
        checked={settings.discoverable_by_phone}
        disabled={update.isPending}
        onChange={(value) => change({ discoverable_by_phone: value })}
      />
    </div>
  );
}
