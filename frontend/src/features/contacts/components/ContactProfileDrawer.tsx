import { zodResolver } from "@hookform/resolvers/zod";
import { MessageCircle, Star } from "lucide-react";
import { Link } from "react-router-dom";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Avatar } from "@/components/shared/Avatar";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { PresenceIndicator } from "@/components/shared/PresenceIndicator";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { QueryError } from "@/features/contacts/components/QueryError";
import {
  useAddToGroup,
  useBlockUser,
  useContactDetail,
  useGroups,
  useRemoveContact,
  useRemoveFromGroup,
  useUpdateContact,
} from "@/features/contacts/hooks/useContacts";
import {
  nicknameSchema,
  type NicknameInput,
  type NicknameValues,
} from "@/features/contacts/schemas";
import type { ContactDetail } from "@/features/contacts/types";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: "medium" });
}

function NicknameForm({ contact }: { contact: ContactDetail }) {
  const update = useUpdateContact();
  const form = useForm<NicknameInput, unknown, NicknameValues>({
    resolver: zodResolver(nicknameSchema),
    defaultValues: { nickname: contact.nickname ?? "" },
  });
  const submit = form.handleSubmit((values) =>
    update.mutate({ id: contact.id, changes: { nickname: values.nickname } }),
  );
  return (
    <form noValidate onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <div className="min-w-0 flex-1">
        <FormField
          label="Nickname"
          hint="Only you see this."
          error={form.formState.errors.nickname?.message}
        >
          <Input autoComplete="off" {...form.register("nickname")} />
        </FormField>
      </div>
      <Button
        type="submit"
        variant="secondary"
        disabled={!form.formState.isDirty || update.isPending}
      >
        Save
      </Button>
    </form>
  );
}

function GroupChecklist({ contact }: { contact: ContactDetail }) {
  const groups = useGroups();
  const add = useAddToGroup();
  const remove = useRemoveFromGroup();
  if (groups.isPending) return <p role="status">Loading groups…</p>;
  if (groups.isError) {
    return <QueryError error={groups.error} onRetry={() => void groups.refetch()} />;
  }
  if (groups.data.length === 0) {
    return <p className="text-sm text-fg-muted">No groups yet. Use “Manage groups” to make one.</p>;
  }
  return (
    <fieldset className="space-y-1">
      <legend className="text-sm font-medium">Groups</legend>
      {groups.data.map((group) => {
        const member = contact.group_ids.includes(group.id);
        return (
          <label key={group.id} className="flex min-h-11 items-center gap-3 text-sm">
            <input
              type="checkbox"
              className="size-5"
              checked={member}
              disabled={add.isPending || remove.isPending}
              onChange={() =>
                member
                  ? remove.mutate({ groupId: group.id, contactId: contact.id })
                  : add.mutate({ groupId: group.id, contactId: contact.id })
              }
            />
            {group.name}
          </label>
        );
      })}
    </fieldset>
  );
}

function DrawerBody({ contact, onClose }: { contact: ContactDetail; onClose: () => void }) {
  const update = useUpdateContact();
  const block = useBlockUser();
  const remove = useRemoveContact();
  const [confirm, setConfirm] = useState<"block" | "remove" | null>(null);
  const isSms = contact.contact_type === "sms";
  const failure = update.error ?? block.error ?? remove.error;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Avatar
          name={contact.display_name}
          imageUrl={contact.avatar_url ?? undefined}
          size="lg"
          presence={isSms ? undefined : contact.presence}
        />
        <div className="min-w-0">
          <DialogTitle className="truncate text-lg font-semibold">
            {contact.display_name}
          </DialogTitle>
          {contact.username ? (
            <p className="truncate text-sm text-fg-muted">@{contact.username}</p>
          ) : null}
          {isSms ? (
            <p className="text-sm text-fg-muted">SMS only · {contact.masked_phone}</p>
          ) : (
            <PresenceIndicator status={contact.presence} showLabel />
          )}
        </div>
      </div>
      <DialogDescription className="sr-only">
        Profile and settings for {contact.display_name}
      </DialogDescription>

      {failure ? (
        <FormAlert tone="error" requestId={toUserFacingError(failure).requestId}>
          {toUserFacingError(failure).message}
        </FormAlert>
      ) : null}

      {contact.status_message ? <p className="text-sm">{contact.status_message}</p> : null}
      {contact.bio ? <p className="text-sm text-fg-muted">{contact.bio}</p> : null}
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        {contact.country_code ? (
          <>
            <dt className="text-fg-muted">Country</dt>
            <dd>{contact.country_code}</dd>
          </>
        ) : null}
        {contact.last_seen_at ? (
          <>
            <dt className="text-fg-muted">Last seen</dt>
            <dd>{new Date(contact.last_seen_at).toLocaleString()}</dd>
          </>
        ) : null}
        <dt className="text-fg-muted">Contact since</dt>
        <dd>{formatDate(contact.added_at)}</dd>
      </dl>

      <div className="flex flex-wrap gap-2">
        {contact.user_id ? (
          <Button asChild>
            <Link to={`${paths.newMessage}?user=${encodeURIComponent(contact.user_id)}`}>
              <MessageCircle aria-hidden className="size-4" />
              Message
            </Link>
          </Button>
        ) : null}
        {isSms ? (
          <Button asChild>
            <Link to={`${paths.smsNew}?contact=${encodeURIComponent(contact.id)}`}>
              <MessageCircle aria-hidden className="size-4" />
              Send SMS
            </Link>
          </Button>
        ) : null}
        <Button
          variant="secondary"
          aria-pressed={contact.is_favourite}
          disabled={update.isPending}
          onClick={() =>
            update.mutate({ id: contact.id, changes: { is_favourite: !contact.is_favourite } })
          }
        >
          <Star
            aria-hidden
            className={contact.is_favourite ? "size-4 fill-away text-away" : "size-4"}
          />
          {contact.is_favourite ? "Remove from favourites" : "Add to favourites"}
        </Button>
      </div>

      <NicknameForm key={contact.nickname ?? ""} contact={contact} />
      <GroupChecklist contact={contact} />

      <div className="flex flex-wrap gap-2 border-t border-border pt-4">
        <Button variant="secondary" onClick={() => setConfirm("remove")}>
          Remove contact
        </Button>
        {contact.user_id ? (
          <Button variant="destructive" onClick={() => setConfirm("block")}>
            Block
          </Button>
        ) : null}
      </div>

      <ConfirmDialog
        open={confirm === "block"}
        onOpenChange={(open) => setConfirm(open ? "block" : null)}
        title={`Block ${contact.display_name}?`}
        description="They will no longer be able to message you, send you requests or see when you are online. They are not told they were blocked. You can unblock them at any time from the Blocked tab."
        confirmLabel="Block"
        destructive
        onConfirm={() => {
          if (contact.user_id) block.mutate(contact.user_id, { onSuccess: onClose });
        }}
      />
      <ConfirmDialog
        open={confirm === "remove"}
        onOpenChange={(open) => setConfirm(open ? "remove" : null)}
        title={`Remove ${contact.display_name}?`}
        description={
          isSms
            ? "This deletes the saved number from your contacts."
            : "You will no longer be contacts. Either of you can send a new request later."
        }
        confirmLabel="Remove"
        destructive
        onConfirm={() => remove.mutate(contact.id, { onSuccess: onClose })}
      />
    </div>
  );
}

export interface ContactProfileDrawerProps {
  contactId: string | null;
  onClose: () => void;
}

/** Side panel with a contact's profile, favourite, nickname, groups, block and remove. */
export function ContactProfileDrawer({ contactId, onClose }: ContactProfileDrawerProps) {
  const detail = useContactDetail(contactId);
  return (
    <Dialog open={contactId !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="left-auto right-0 top-0 h-full max-w-sm translate-x-0 translate-y-0 overflow-y-auto rounded-none">
        {detail.isPending ? <p role="status">Loading contact…</p> : null}
        {detail.isError ? (
          <>
            <DialogTitle className="sr-only">Contact</DialogTitle>
            <DialogDescription className="sr-only">Contact could not be loaded</DialogDescription>
            <QueryError error={detail.error} onRetry={() => void detail.refetch()} />
          </>
        ) : null}
        {detail.data ? <DrawerBody contact={detail.data} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}
