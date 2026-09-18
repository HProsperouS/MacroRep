import { CircleUser, LogOut } from "lucide-react"
import { NavLink, useNavigate } from "react-router-dom"

import { NAV_ITEMS } from "@/components/layout/nav-items"
import { useLogout } from "@/hooks/use-auth"
import { cn } from "@/lib/utils"

export function SidebarNav({ className }: { className?: string }) {
  const navigate = useNavigate()
  const logout = useLogout()

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
      <NavLink
        to="/profile"
        className={({ isActive }) =>
          cn(
            "mt-auto flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
            isActive && "bg-sidebar-accent text-sidebar-accent-foreground [&_svg]:text-primary",
          )
        }
      >
        <CircleUser className="size-5" aria-hidden />
        Profile
      </NavLink>
      <button
        type="button"
        disabled={logout.isPending}
        onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login", { replace: true }) })}
        className="flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground disabled:opacity-50"
      >
        <LogOut className="size-5" aria-hidden />
        Sign out
      </button>
    </aside>
  )
}
