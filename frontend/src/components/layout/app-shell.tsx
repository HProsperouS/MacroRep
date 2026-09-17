import { Outlet } from "react-router-dom"

import { BottomTabBar } from "@/components/layout/bottom-tab-bar"
import { SidebarNav } from "@/components/layout/sidebar-nav"

/** Sidebar on md+ screens, bottom tab bar on mobile. */
export function AppShell() {
  return (
    <div className="flex min-h-dvh bg-background">
      <SidebarNav className="hidden md:flex" />
      <main className="flex min-w-0 flex-1 flex-col gap-4 px-4 pt-5 pb-28 md:gap-6 md:px-9 md:py-7">
        <Outlet />
      </main>
      <BottomTabBar className="md:hidden" />
    </div>
  )
}
