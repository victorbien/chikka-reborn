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
  { to: paths.sms, label: "SMS" },
  { to: paths.contacts, label: "Contacts" },
  { to: paths.styleGuide, label: "Style guide" },
];

/** Shown to administrators in addition to the main items. */
export const ADMIN_NAV_ITEMS: readonly NavItem[] = [{ to: paths.admin, label: "Admin" }];

export interface MainNavProps {
  items?: readonly NavItem[];
  /** Classic mode: a menu-bar look. Touch targets stay 44px on small screens. */
  compact?: boolean;
  className?: string;
}

export function MainNav({ items = MAIN_NAV_ITEMS, compact = false, className }: MainNavProps) {
  return (
    <nav aria-label="Main" className={cn("flex gap-1", className)}>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === paths.home}
          className={({ isActive }) =>
            cn(
              "inline-flex min-h-11 shrink-0 items-center whitespace-nowrap rounded-control px-3 text-sm font-medium transition-colors hover:bg-surface-raised",
              compact && "px-2 text-xs md:min-h-8",
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
