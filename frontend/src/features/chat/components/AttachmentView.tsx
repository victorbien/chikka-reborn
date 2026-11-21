import { FileText } from "lucide-react";
import { formatSize } from "@/features/chat/format";
import type { Attachment } from "@/features/chat/types";

/** Images show as thumbnails (alt text is the file name); other files as a download chip. */
export function AttachmentView({ attachment }: { attachment: Attachment }) {
  const isImage = attachment.content_type.startsWith("image/");
  if (!attachment.url) {
    return (
      <p className="mt-1 text-xs opacity-80">
        {attachment.file_name} ({formatSize(attachment.size_bytes)}), unavailable right now
      </p>
    );
  }
  if (isImage) {
    return (
      <a href={attachment.url} target="_blank" rel="noreferrer noopener" className="mt-1 block">
        <img
          src={attachment.url}
          alt={attachment.file_name}
          loading="lazy"
          className="max-h-60 max-w-full rounded-control object-contain"
        />
      </a>
    );
  }
  return (
    <a
      href={attachment.url}
      target="_blank"
      rel="noreferrer noopener"
      className="mt-1 flex min-h-11 items-center gap-2 rounded-control border border-border px-2 py-1 text-sm underline-offset-2 hover:underline"
    >
      <FileText aria-hidden className="size-4 shrink-0" />
      <span className="truncate">{attachment.file_name}</span>
      <span className="shrink-0 text-xs opacity-80">{formatSize(attachment.size_bytes)}</span>
    </a>
  );
}
