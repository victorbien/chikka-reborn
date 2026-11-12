import { MessagesSquare } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { Button } from "@/components/ui/button";
import { ConversationList } from "@/features/chat/components/ConversationList";
import { ConversationView } from "@/features/chat/components/ConversationView";
import { useOpenConversation } from "@/features/chat/hooks/useChat";
import { useMe } from "@/features/profile/hooks/useProfile";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";
import { cn } from "@/lib/utils";

/** Messages (Module C): the conversation list, and the open conversation beside it. On small
 *  screens only one of the two is shown. */
export function MessagesPage() {
  const { conversationId } = useParams();
  const me = useMe();
  const viewerId = me.data?.id;

  return (
    <div className="grid gap-4 md:grid-cols-[18rem_1fr]">
      <h1 className="sr-only">Messages</h1>
      <div className={cn(conversationId ? "hidden md:block" : "block")}>
        <ConversationList selectedId={conversationId} />
      </div>
      <div
        className={cn(
          "rounded-panel border border-border bg-surface",
          conversationId ? "block" : "hidden md:block",
        )}
      >
        {conversationId && viewerId ? (
          <ConversationView
            key={conversationId}
            conversationId={conversationId}
            viewerId={viewerId}
          />
        ) : (
          <EmptyState
            icon={MessagesSquare}
            title="Choose a conversation"
            description="Or open a contact and choose Message."
            action={
              <Button asChild variant="secondary">
                <Link to={paths.contacts}>Go to contacts</Link>
              </Button>
            }
          />
        )}
      </div>
    </div>
  );
}

/** /messages/new?user=<id>: opens (or creates) the conversation with that contact. */
export function NewConversationPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const userId = params.get("user");
  const open = useOpenConversation();
  const started = useRef(false);
  const { mutate } = open;

  useEffect(() => {
    if (!userId || started.current) return;
    started.current = true;
    mutate(userId, {
      onSuccess: (summary) => navigate(`${paths.messages}/${summary.id}`, { replace: true }),
    });
  }, [userId, mutate, navigate]);

  if (!userId) return <Navigate to={paths.messages} replace />;
  if (open.isError) {
    const friendly = toUserFacingError(open.error);
    return (
      <ErrorState
        kind="error"
        message={
          friendly.kind === "forbidden" ? "You can only message your contacts." : friendly.message
        }
        requestId={friendly.requestId}
      />
    );
  }
  return <p role="status">Opening conversation…</p>;
}
