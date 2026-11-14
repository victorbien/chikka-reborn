import { MessageSquareText } from "lucide-react";
import { useParams } from "react-router-dom";
import { EmptyState } from "@/components/shared/EmptyState";
import { LowCreditWarning } from "@/features/credits/components/LowCreditWarning";
import { NewSmsForm } from "@/features/sms/components/NewSmsForm";
import { SmsConversationList } from "@/features/sms/components/SmsConversationList";
import { SmsConversationView } from "@/features/sms/components/SmsConversationView";
import { SmsModeBanner } from "@/features/sms/components/SmsModeBanner";
import { cn } from "@/lib/utils";

/** SMS (Modules D and E): conversations with mobile numbers, replies included. */
export function SmsPage({ mode }: { mode: "list" | "new" | "conversation" }) {
  const { conversationId } = useParams();
  const showDetail = mode !== "list";
  return (
    <div>
      <h1 className="sr-only">SMS</h1>
      <SmsModeBanner />
      <LowCreditWarning />
      <div className="grid gap-4 md:grid-cols-[18rem_1fr]">
        <div className={cn(showDetail ? "hidden md:block" : "block")}>
          <SmsConversationList selectedId={conversationId} />
        </div>
        <div
          className={cn(
            "rounded-panel border border-border bg-surface",
            showDetail ? "block" : "hidden md:block",
          )}
        >
          {mode === "conversation" && conversationId ? (
            <SmsConversationView key={conversationId} conversationId={conversationId} />
          ) : mode === "new" ? (
            <NewSmsForm />
          ) : (
            <EmptyState
              icon={MessageSquareText}
              title="Choose a conversation"
              description="Or start a new SMS to a mobile number."
            />
          )}
        </div>
      </div>
    </div>
  );
}
