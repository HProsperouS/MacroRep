import { NavLink } from "react-router-dom"

import { NAV_ITEMS } from "@/components/layout/nav-items"
import { cn } from "@/lib/utils"

export function SidebarNav({ className }: { className?: string }) {
  return (
    <aside
      className={cn(
        "sticky top-0 h-dvh w-62 shrink-0 flex-col gap-7 border-r border-sidebar-border bg-sidebar px-4 py-6",
        className,
      )}
    >
      <span className="font-display text-2xl font-semibold tracking-wide text-foreground">MACROREP</span>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                isActive && "bg-sidebar-accent text-sidebar-accent-foreground [&_svg]:text-primary",
              )
            }
          >
            <Icon className="size-5" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
