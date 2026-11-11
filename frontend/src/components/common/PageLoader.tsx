import { Loader2 } from "lucide-react";

export interface PageLoaderProps {
  label?: string;
}

export function PageLoader({ label = "Loading" }: PageLoaderProps) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 p-8 text-fg-muted">
      <Loader2 aria-hidden className="size-5 animate-spin" />
      <span>{label}…</span>
    </div>
  );
}
