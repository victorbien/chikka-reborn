import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { QueryError } from "@/features/contacts/components/QueryError";
import {
  useCreateGroup,
  useDeleteGroup,
  useGroups,
  useRenameGroup,
} from "@/features/contacts/hooks/useContacts";
import {
  groupNameSchema,
  type GroupNameInput,
  type GroupNameValues,
} from "@/features/contacts/schemas";
import type { ContactGroup } from "@/features/contacts/types";
import { toUserFacingError } from "@/lib/error-handling";
import { applyServerFieldErrors } from "@/lib/forms";

function NameForm({
  initial,
  label,
  submitLabel,
  pending,
  onSubmit,
  onCancel,
  serverError,
}: {
  initial: string;
  label: string;
  submitLabel: string;
  pending: boolean;
  onSubmit: (name: string) => Promise<unknown>;
  onCancel?: () => void;
  serverError?: unknown;
}) {
  const form = useForm<GroupNameInput, unknown, GroupNameValues>({
    resolver: zodResolver(groupNameSchema),
    defaultValues: { name: initial },
  });
  const submit = form.handleSubmit(async (values) => {
    try {
      await onSubmit(values.name);
      form.reset({ name: "" });
    } catch (error) {
      applyServerFieldErrors(error, form.setError, ["name"]);
    }
  });
  const serverMessage = serverError ? toUserFacingError(serverError).message : undefined;
  return (
    <form noValidate onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <div className="min-w-0 flex-1">
        <FormField label={label} error={form.formState.errors.name?.message ?? serverMessage}>
          <Input autoComplete="off" maxLength={60} {...form.register("name")} />
        </FormField>
      </div>
      <Button type="submit" disabled={pending}>
        {submitLabel}
      </Button>
      {onCancel ? (
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      ) : null}
    </form>
  );
}

function GroupRow({ group }: { group: ContactGroup }) {
  const rename = useRenameGroup();
  const remove = useDeleteGroup();
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);

  if (editing) {
    return (
      <li>
        <NameForm
          initial={group.name}
          label={`Rename ${group.name}`}
          submitLabel="Save"
          pending={rename.isPending}
          serverError={rename.error}
          onCancel={() => setEditing(false)}
          onSubmit={async (name) => {
            await rename.mutateAsync({ id: group.id, name });
            setEditing(false);
          }}
        />
      </li>
    );
  }
  return (
    <li className="flex items-center gap-2">
      <span className="min-w-0 flex-1 truncate text-sm">
        {group.name}{" "}
        <span className="text-xs text-fg-muted">
          ({group.member_count} {group.member_count === 1 ? "contact" : "contacts"})
        </span>
      </span>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`Rename group ${group.name}`}
        onClick={() => setEditing(true)}
      >
        <Pencil aria-hidden className="size-4" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`Delete group ${group.name}`}
        onClick={() => setConfirming(true)}
      >
        <Trash2 aria-hidden className="size-4" />
      </Button>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Delete the group "${group.name}"?`}
        description="The contacts in this group are kept. Only the group is removed."
        confirmLabel="Delete group"
        destructive
        onConfirm={() => remove.mutate(group.id)}
      />
    </li>
  );
}

/** Create, rename and delete contact groups. Groups are private labels, not group chats. */
export function GroupManager() {
  const groups = useGroups();
  const create = useCreateGroup();

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          Manage groups
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle className="text-lg font-semibold">Contact groups</DialogTitle>
        <DialogDescription className="mt-1 text-sm text-fg-muted">
          Only you can see your groups. You can have up to 20.
        </DialogDescription>
        <div className="mt-4 space-y-4">
          <NameForm
            initial=""
            label="New group name"
            submitLabel="Create group"
            pending={create.isPending}
            serverError={create.error}
            onSubmit={(name) => create.mutateAsync(name)}
          />
          {groups.isPending ? <p role="status">Loading groups…</p> : null}
          {groups.isError ? (
            <QueryError error={groups.error} onRetry={() => void groups.refetch()} />
          ) : null}
          {groups.data && groups.data.length === 0 ? (
            <FormAlert tone="info">You have no groups yet.</FormAlert>
          ) : null}
          {groups.data && groups.data.length > 0 ? (
            <ul className="space-y-2">
              {groups.data.map((group) => (
                <GroupRow key={group.id} group={group} />
              ))}
            </ul>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
