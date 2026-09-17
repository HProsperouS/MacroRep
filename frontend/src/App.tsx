import { lazy, Suspense } from "react"
import { Route, Routes } from "react-router-dom"

import { AppShell } from "@/components/layout/app-shell"

const HomePage = lazy(() => import("@/pages/home-page"))
const FoodPage = lazy(() => import("@/pages/food-page"))
const WorkoutPage = lazy(() => import("@/pages/workout-page"))
const CoachPage = lazy(() => import("@/pages/coach-page"))
const ProgressPage = lazy(() => import("@/pages/progress-page"))
const ProfilePage = lazy(() => import("@/pages/profile-page"))
const NotFoundPage = lazy(() => import("@/pages/not-found-page"))

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="food" element={<FoodPage />} />
          <Route path="workout" element={<WorkoutPage />} />
          <Route path="coach" element={<CoachPage />} />
          <Route path="progress" element={<ProgressPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
