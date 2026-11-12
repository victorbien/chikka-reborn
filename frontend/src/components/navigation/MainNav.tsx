import { NavLink } from "react-router-dom";
import { paths } from "@/lib/paths";
import { cn } from "@/lib/utils";

export interface NavItem {
  to: string;
  label: string;
}

/** Shown to visitors who are not signed in. */
export const PUBLIC_NAV_ITEMS: readonly NavItem[] = [
  { to: paths.signIn, label: "Sign in" },
  { to: paths.styleGuide, label: "Style guide" },
];

/** Only routes that exist today. Module entries are added as their features land. */
export const MAIN_NAV_ITEMS: readonly NavItem[] = [
  { to: paths.home, label: "Home" },
  { to: paths.messages, label: "Messages" },
  { to: paths.contacts, label: "Contacts" },
  { to: paths.settings, label: "Settings" },
  { to: paths.styleGuide, label: "Style guide" },
];

export function MainNav({ items = MAIN_NAV_ITEMS }: { items?: readonly NavItem[] }) {
  return (
    <nav aria-label="Main" className="flex flex-wrap gap-1">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === paths.home}
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
