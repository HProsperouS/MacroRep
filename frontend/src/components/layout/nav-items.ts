import { CircleUser, Dumbbell, House, Sparkles, TrendingUp, UtensilsCrossed, type LucideIcon } from "lucide-react"

type NavItem = {
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

export const PROFILE_ITEM: NavItem = { label: "Profile", to: "/profile", icon: CircleUser }
