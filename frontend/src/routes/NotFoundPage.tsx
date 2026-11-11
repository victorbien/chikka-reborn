import { Link } from "react-router-dom";
import { SearchX } from "lucide-react";
import { EmptyState } from "@/components/shared/EmptyState";

export function NotFoundPage() {
  return (
    <EmptyState
      icon={SearchX}
      title="Page not found"
      description="That address does not exist."
      action={
        <Link to="/" className="text-accent underline">
          Back to home
        </Link>
      }
    />
  );
}
