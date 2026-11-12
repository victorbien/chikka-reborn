import { UserPlus } from "lucide-react";
import { useState } from "react";
import { FormAlert } from "@/components/common/FormAlert";
import { Avatar } from "@/components/shared/Avatar";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { QueryError } from "@/features/contacts/components/QueryError";
import {
  useAcceptRequest,
  useCancelRequest,
  useRejectRequest,
  useRequests,
} from "@/features/contacts/hooks/useContacts";
import type { ContactRequestItem } from "@/features/contacts/types";
import { toUserFacingError } from "@/lib/error-handling";

function RequestRow({ request }: { request: ContactRequestItem }) {
  const accept = useAcceptRequest();
  const reject = useRejectRequest();
  const cancel = useCancelRequest();
  const busy = accept.isPending || reject.isPending || cancel.isPending;
  const failure = accept.error ?? reject.error ?? cancel.error;
  const name = request.person.display_name;

  return (
    <li className="space-y-2 rounded-panel border border-border p-3">
      <div className="flex items-center gap-3">
        <Avatar name={name} imageUrl={request.person.avatar_url ?? undefined} size="sm" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{name}</p>
          {request.person.username ? (
            <p className="truncate text-xs text-fg-muted">@{request.person.username}</p>
          ) : null}
        </div>
      </div>
      {request.note ? <p className="text-sm">“{request.note}”</p> : null}
      <p className="text-xs text-fg-muted">
        {request.direction === "incoming" ? "Received" : "Sent"}{" "}
        {new Date(request.created_at).toLocaleDateString()}
      </p>
      {failure ? (
        <FormAlert tone="error" requestId={toUserFacingError(failure).requestId}>
          {toUserFacingError(failure).message}
        </FormAlert>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {request.direction === "incoming" ? (
          <>
            <Button
              size="sm"
              disabled={busy}
              aria-label={`Accept request from ${name}`}
              onClick={() => accept.mutate({ requestId: request.id })}
            >
              Accept
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy}
              aria-label={`Reject request from ${name}`}
              onClick={() => reject.mutate({ requestId: request.id, block: false })}
            >
              Reject
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              aria-label={`Reject and block ${name}`}
              onClick={() => reject.mutate({ requestId: request.id, block: true })}
            >
              Reject and block
            </Button>
          </>
        ) : (
          <Button
            size="sm"
            variant="secondary"
            disabled={busy}
            aria-label={`Cancel request to ${name}`}
            onClick={() => cancel.mutate(request.id)}
          >
            Cancel request
          </Button>
        )}
      </div>
    </li>
  );
}

function RequestList({ direction }: { direction: "incoming" | "outgoing" }) {
  const [page, setPage] = useState(1);
  const requests = useRequests(direction, page);

  if (requests.isPending) return <p role="status">Loading requests…</p>;
  if (requests.isError) {
    return <QueryError error={requests.error} onRetry={() => void requests.refetch()} />;
  }
  if (requests.data.data.length === 0) {
    return (
      <EmptyState
        icon={UserPlus}
        title={direction === "incoming" ? "No requests waiting" : "No requests sent"}
        description={
          direction === "incoming"
            ? "When someone asks to be your contact, it shows up here."
            : "Requests you send stay here until they are answered or expire after 30 days."
        }
      />
    );
  }
  const { pagination } = requests.data;
  return (
    <div className="space-y-3">
      <ul className="space-y-2">
        {requests.data.data.map((request) => (
          <RequestRow key={request.id} request={request} />
        ))}
      </ul>
      {pagination.has_prev || pagination.has_next ? (
        <div className="flex justify-between">
          <Button
            size="sm"
            variant="secondary"
            disabled={!pagination.has_prev}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={!pagination.has_next}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </div>
  );
}

/** Incoming and outgoing contact requests (FR-CONTACTS-009, 010). */
export function ContactRequestsPanel() {
  const [direction, setDirection] = useState<"incoming" | "outgoing">("incoming");
  return (
    <div className="space-y-3">
      <div role="group" aria-label="Request direction" className="flex gap-2">
        {(["incoming", "outgoing"] as const).map((value) => (
          <Button
            key={value}
            size="sm"
            variant={direction === value ? "primary" : "secondary"}
            aria-pressed={direction === value}
            onClick={() => setDirection(value)}
          >
            {value === "incoming" ? "Received" : "Sent"}
          </Button>
        ))}
      </div>
      <RequestList key={direction} direction={direction} />
    </div>
  );
}
