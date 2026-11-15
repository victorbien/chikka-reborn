import { useEffect, useRef } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ErrorState } from "@/components/shared/ErrorState";
import { useOpenConversation } from "@/features/chat/hooks/useChat";
import { useMe } from "@/features/profile/hooks/useProfile";
import { useDisplayMode } from "@/lib/display-mode";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";
import { ClassicMessenger } from "@/routes/modes/ClassicMessenger";
import { ModernMessenger } from "@/routes/modes/ModernMessenger";

/** Messages (Module C) in the user's chosen interface. On small screens only one pane shows. */
export function MessagesPage() {
  const { conversationId } = useParams();
  const { mode } = useDisplayMode();
  const me = useMe();
  const viewerId = me.data?.id;

  // Same data and services in both modes; only the layout differs.
  return mode === "classic" ? (
    <ClassicMessenger conversationId={conversationId} viewerId={viewerId} />
  ) : (
    <ModernMessenger conversationId={conversationId} viewerId={viewerId} />
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
