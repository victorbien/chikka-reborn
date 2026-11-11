import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

export interface NavItem {
  to: string;
  label: string;
}

/** Only routes that exist today. Module entries are added as their features land. */
export const MAIN_NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "Home" },
  { to: "/style-guide", label: "Style guide" },
];

export function MainNav() {
  return (
    <nav aria-label="Main" className="flex gap-1">
      {MAIN_NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          className={({ isActive }) =>
            cn(
              "inline-flex min-h-11 items-center rounded-control px-3 text-sm font-medium hover:bg-surface-raised",
              isActive ? "bg-surface-raised text-accent" : "text-fg",
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
