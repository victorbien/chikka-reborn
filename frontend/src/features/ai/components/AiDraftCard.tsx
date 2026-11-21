import { Check, Pencil, X } from "lucide-react";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";

export interface AiDraftCardProps {
  text: string;
  /** Puts the text in the message box. The user still has to press Send. */
  onAccept: (text: string, edited: boolean) => void;
  onReject: () => void;
  /** False for results that are read-only, such as a summary. */
  canUse?: boolean;
}

/** One AI draft with accept, edit and reject. Nothing here sends anything. */
export function AiDraftCard({ text, onAccept, onReject, canUse = true }: AiDraftCardProps) {
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState(text);
  const editorId = useId();

  return (
    <li className="rounded-control border border-border bg-canvas p-2">
      {editing ? (
        <div>
          <label htmlFor={editorId} className="sr-only">
            Edit the AI draft
          </label>
          <Textarea id={editorId} value={edited} onChange={(e) => setEdited(e.target.value)} />
        </div>
      ) : (
        <p className="whitespace-pre-wrap text-sm">{text}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        {canUse ? (
          editing ? (
            <Button
              size="sm"
              disabled={edited.trim().length === 0}
              onClick={() => onAccept(edited.trim(), true)}
            >
              <Check aria-hidden className="size-4" />
              Use edited text
            </Button>
          ) : (
            <>
              <Button size="sm" onClick={() => onAccept(text, false)}>
                <Check aria-hidden className="size-4" />
                Use
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
                <Pencil aria-hidden className="size-4" />
                Edit
              </Button>
            </>
          )
        ) : null}
        <Button size="sm" variant="ghost" onClick={onReject}>
          <X aria-hidden className="size-4" />
          {canUse ? "Reject" : "Close"}
        </Button>
      </div>
    </li>
  );
}
