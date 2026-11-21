import { Outlet, useLocation } from "react-router-dom"

import { BottomTabBar } from "@/components/layout/bottom-tab-bar"
import { ErrorBoundary } from "@/components/layout/error-boundary"
import { SidebarNav } from "@/components/layout/sidebar-nav"
import { useSyncTimezone } from "@/hooks/use-profile"

/** Sidebar on md+ screens, bottom tab bar on mobile. */
export function AppShell() {
  useSyncTimezone()
  const { pathname } = useLocation()

  return (
    <div className="flex min-h-dvh bg-background">
      <SidebarNav className="hidden md:flex" />
      <main className="flex min-w-0 flex-1 flex-col gap-4 px-4 pt-5 pb-28 md:gap-6 md:px-9 md:py-7">
        {/* A page that breaks keeps the navigation; going to another page starts afresh. */}
        <ErrorBoundary key={pathname}>
          <Outlet />
        </ErrorBoundary>
      </main>
      <BottomTabBar className="md:hidden" />
    </div>
  )
}
