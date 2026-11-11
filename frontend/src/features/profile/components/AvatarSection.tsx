import { useRef, useState } from "react";
import { Avatar } from "@/components/shared/Avatar";
import { FormAlert } from "@/components/common/FormAlert";
import { Button } from "@/components/ui/button";
import { useRemoveAvatar, useUploadAvatar } from "@/features/profile/hooks/useProfile";
import type { Profile } from "@/features/profile/types";
import { isApiError } from "@/lib/api/errors";
import { toUserFacingError } from "@/lib/error-handling";

const MAX_BYTES = 2 * 1024 * 1024;
const ACCEPT = ["image/jpeg", "image/png", "image/webp"];

/** Profile photo (FR-AUTH-011). The server re-checks the file and strips metadata. */
export function AvatarSection({ profile }: { profile: Profile }) {
  const input = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const upload = useUploadAvatar();
  const remove = useRemoveAvatar();

  const onFile = (file: File | undefined) => {
    setLocalError(null);
    upload.reset();
    if (!file) return;
    if (!ACCEPT.includes(file.type)) {
      setLocalError("Use a JPEG, PNG or WebP image.");
    } else if (file.size > MAX_BYTES) {
      setLocalError("The image must be 2 MB or smaller.");
    } else {
      upload.mutate(file);
    }
    if (input.current) input.current.value = "";
  };

  // 422 messages from the image check are specific and safe to show as-is.
  const uploadMessage = upload.error
    ? isApiError(upload.error) && upload.error.status === 422
      ? upload.error.message
      : toUserFacingError(upload.error).message
    : null;
  const serverMessage = localError ?? uploadMessage;

  return (
    <div className="flex flex-wrap items-center gap-4">
      <Avatar name={profile.display_name} imageUrl={profile.avatar_url ?? undefined} size="lg" />
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={upload.isPending}
            onClick={() => input.current?.click()}
          >
            {upload.isPending ? "Uploading…" : profile.avatar_url ? "Change photo" : "Upload photo"}
          </Button>
          {profile.avatar_url ? (
            <Button variant="ghost" disabled={remove.isPending} onClick={() => remove.mutate()}>
              Remove
            </Button>
          ) : null}
        </div>
        <input
          ref={input}
          type="file"
          accept={ACCEPT.join(",")}
          className="sr-only"
          aria-label="Choose a profile photo"
          onChange={(event) => onFile(event.target.files?.[0])}
        />
        <p className="text-xs text-fg-muted">
          JPEG, PNG or WebP, up to 2 MB. Location data is removed.
        </p>
        {upload.isSuccess ? <FormAlert tone="success">Photo updated.</FormAlert> : null}
        {serverMessage ? <FormAlert tone="error">{serverMessage}</FormAlert> : null}
        {remove.error ? (
          <FormAlert tone="error">{toUserFacingError(remove.error).message}</FormAlert>
        ) : null}
      </div>
    </div>
  );
}
