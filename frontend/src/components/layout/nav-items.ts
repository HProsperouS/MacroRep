import { Dumbbell, House, Sparkles, TrendingUp, UtensilsCrossed, type LucideIcon } from "lucide-react"

export type NavItem = {
  label: string
  to: string
  icon: LucideIcon
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Home", to: "/", icon: House },
  { label: "Food", to: "/food", icon: UtensilsCrossed },
  { label: "Workout", to: "/workout", icon: Dumbbell },
  { label: "Coach", to: "/coach", icon: Sparkles },
  { label: "Progress", to: "/progress", icon: TrendingUp },
]
