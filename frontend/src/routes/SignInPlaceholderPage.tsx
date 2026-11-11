import { Link } from "react-router-dom";
import { EmptyState } from "@/components/shared/EmptyState";
import { LogIn } from "lucide-react";

/** Placeholder inside the auth layout. Real sign-in is Phase 1 (Module A). */
export function SignInPlaceholderPage() {
  return (
    <EmptyState
      icon={LogIn}
      title="Sign-in is not available yet"
      description="Accounts arrive in Phase 1. Nothing here can sign you in."
      action={
        <Link to="/" className="text-accent underline">
          Back to home
        </Link>
      }
    />
  );
}
