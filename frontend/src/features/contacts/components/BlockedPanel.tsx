import { ShieldOff } from "lucide-react";
import { useState } from "react";
import { FormAlert } from "@/components/common/FormAlert";
import { Avatar } from "@/components/shared/Avatar";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { QueryError } from "@/features/contacts/components/QueryError";
import { useBlocks, useUnblockUser } from "@/features/contacts/hooks/useContacts";
import type { BlockItem } from "@/features/contacts/types";
import { toUserFacingError } from "@/lib/error-handling";

function BlockedRow({ block }: { block: BlockItem }) {
  const unblock = useUnblockUser();
  const [confirming, setConfirming] = useState(false);
  const name = block.person.display_name;
  return (
    <li className="space-y-2">
      <div className="flex items-center gap-3">
        <Avatar name={name} imageUrl={block.person.avatar_url ?? undefined} size="sm" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{name}</span>
          {block.person.username ? (
            <span className="block truncate text-xs text-fg-muted">@{block.person.username}</span>
          ) : null}
        </span>
        <Button
          size="sm"
          variant="secondary"
          aria-label={`Unblock ${name}`}
          onClick={() => setConfirming(true)}
        >
          Unblock
        </Button>
      </div>
      {unblock.error ? (
        <FormAlert tone="error">{toUserFacingError(unblock.error).message}</FormAlert>
      ) : null}
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Unblock ${name}?`}
        description="They will be able to find you and send requests again. Messages sent while they were blocked are not delivered later, and a contact you removed is not restored."
        confirmLabel="Unblock"
        onConfirm={() => unblock.mutate(block.user_id)}
      />
    </li>
  );
}

/** People you blocked. Only you can see this list. */
export function BlockedPanel() {
  const blocks = useBlocks();
  if (blocks.isPending) return <p role="status">Loading blocked people…</p>;
  if (blocks.isError) {
    return <QueryError error={blocks.error} onRetry={() => void blocks.refetch()} />;
  }
  if (blocks.data.length === 0) {
    return (
      <EmptyState
        icon={ShieldOff}
        title="Nobody is blocked"
        description="People you block can't message you or see when you are online. They are never told."
      />
    );
  }
  return (
    <ul className="space-y-3">
      {blocks.data.map((block) => (
        <BlockedRow key={block.user_id} block={block} />
      ))}
    </ul>
  );
}
