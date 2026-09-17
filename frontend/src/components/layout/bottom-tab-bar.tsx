import { NavLink } from "react-router-dom"

import { NAV_ITEMS } from "@/components/layout/nav-items"
import { cn } from "@/lib/utils"

export function BottomTabBar({ className }: { className?: string }) {
  return (
    <nav
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 flex border-t border-border bg-background/95 px-2 pb-[max(env(safe-area-inset-bottom),0.5rem)] backdrop-blur",
        className,
      )}
    >
      {NAV_ITEMS.map(({ label, to, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) =>
            cn(
              "flex h-16 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium text-muted-foreground",
              isActive && "text-primary",
            )
          }
        >
          <Icon className="size-[22px]" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
