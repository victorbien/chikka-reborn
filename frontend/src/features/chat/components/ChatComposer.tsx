import { X } from "lucide-react";
import { useState } from "react";
import { FormAlert } from "@/components/common/FormAlert";
import { MessageComposer } from "@/components/shared/MessageComposer";
import { formatSize } from "@/features/chat/format";
import { useTypingSignal, useUploadAttachment } from "@/features/chat/hooks/useChat";
import type { Attachment } from "@/features/chat/types";
import { toUserFacingError } from "@/lib/error-handling";

export const MAX_CHARS = 2000;
const MAX_FILES = 5;
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ACCEPT = "image/jpeg,image/png,image/webp,image/gif,application/pdf";
const ALLOWED = new Set(ACCEPT.split(","));

export interface ChatComposerProps {
  conversationId: string;
  onSend: (body: string, attachments: Attachment[]) => void;
  disabledReason?: string;
}

/** Text, emoji and attachments. Files upload when picked, so Send only links them. */
export function ChatComposer({ conversationId, onSend, disabledReason }: ChatComposerProps) {
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState<Attachment[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [uploading, setUploading] = useState(0);
  const upload = useUploadAttachment(conversationId);
  const typing = useTypingSignal(conversationId);

  async function attach(picked: File[]) {
    setProblem(null);
    const room = MAX_FILES - files.length - uploading;
    if (picked.length > room) {
      setProblem(`You can attach up to ${MAX_FILES} files to one message.`);
    }
    for (const file of picked.slice(0, Math.max(0, room))) {
      // A quick check here for a fast answer. The server checks the real content.
      if (file.type && !ALLOWED.has(file.type)) {
        setProblem(`${file.name}: use a JPEG, PNG, WebP or GIF image, or a PDF.`);
        continue;
      }
      if (file.size > MAX_FILE_BYTES) {
        setProblem(`${file.name} is larger than 10 MB.`);
        continue;
      }
      setUploading((n) => n + 1);
      try {
        const attachment = await upload.mutateAsync(file);
        setFiles((current) => [...current, attachment]);
      } catch (error) {
        setProblem(`${file.name}: ${toUserFacingError(error).message}`);
      } finally {
        setUploading((n) => n - 1);
      }
    }
  }

  function send() {
    onSend(draft, files);
    setDraft("");
    setFiles([]);
    setProblem(null);
  }

  return (
    <MessageComposer
      value={draft}
      onChange={setDraft}
      onSend={send}
      channel="internet"
      maxLength={MAX_CHARS}
      emoji
      onTyping={typing}
      onAttach={(picked) => void attach(picked)}
      accept={ACCEPT}
      hasAttachments={files.length > 0}
      sendDisabled={uploading > 0}
      disabledReason={disabledReason}
      autoFocus
      attachments={
        files.length || uploading ? (
          <ul aria-label="Files to send" className="flex flex-wrap gap-2">
            {files.map((file) => (
              <li
                key={file.id}
                className="flex min-h-11 items-center gap-2 rounded-control border border-border px-2 text-xs"
              >
                <span className="max-w-40 truncate">{file.file_name}</span>
                <span className="text-fg-muted">{formatSize(file.size_bytes)}</span>
                <button
                  type="button"
                  aria-label={`Remove ${file.file_name}`}
                  onClick={() => setFiles((current) => current.filter((f) => f.id !== file.id))}
                  className="inline-flex size-8 items-center justify-center rounded-control hover:bg-surface-raised"
                >
                  <X aria-hidden className="size-3.5" />
                </button>
              </li>
            ))}
            {uploading ? (
              <li role="status" className="flex min-h-11 items-center px-2 text-xs text-fg-muted">
                Uploading {uploading === 1 ? "1 file" : `${uploading} files`}…
              </li>
            ) : null}
          </ul>
        ) : null
      }
      error={problem ? <FormAlert tone="error">{problem}</FormAlert> : null}
    />
  );
}
