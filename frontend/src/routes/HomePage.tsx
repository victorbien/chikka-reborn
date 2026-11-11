import { Link } from "react-router-dom";
import { ApiStatusCard } from "@/features/system/components/ApiStatusCard";

export function HomePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Chikka Reborn</h1>
      <p className="text-fg-muted">
        Foundation build. Messaging features arrive in later phases. See the{" "}
        <Link to="/style-guide" className="text-accent underline">
          style guide
        </Link>{" "}
        for the shared components.
      </p>
      <section
        aria-labelledby="api-status-heading"
        className="space-y-2 rounded-panel border border-border bg-surface p-4"
      >
        <h2 id="api-status-heading" className="text-lg font-semibold">
          Server status
        </h2>
        <ApiStatusCard />
      </section>
    </div>
  );
}
