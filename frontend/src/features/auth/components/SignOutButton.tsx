import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLogout } from "@/features/auth/hooks/useAuth";

export function SignOutButton({ onSignedOut }: { onSignedOut: () => void }) {
  const logout = useLogout();
  return (
    <Button
      variant="ghost"
      size="sm"
      disabled={logout.isPending}
      onClick={() => logout.mutate("local", { onSettled: onSignedOut })}
    >
      <LogOut aria-hidden className="size-4" />
      {logout.isPending ? "Signing out…" : "Sign out"}
    </Button>
  );
}
