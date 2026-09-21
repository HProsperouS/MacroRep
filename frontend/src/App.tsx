import { lazy, Suspense, useEffect, useState, type ReactNode } from "react"
import { Navigate, Route, Routes } from "react-router-dom"

import { restoreSession } from "@/api/client"
import { AppShell } from "@/components/layout/app-shell"
import { Spinner } from "@/components/ui/spinner"
import { getAccessToken } from "@/lib/auth"

const HomePage = lazy(() => import("@/pages/home-page"))
const FoodPage = lazy(() => import("@/pages/food-page"))
const WorkoutPage = lazy(() => import("@/pages/workout-page"))
const WorkoutPlanPage = lazy(() => import("@/pages/workout-plan-page"))
const CoachPage = lazy(() => import("@/pages/coach-page"))
const ProgressPage = lazy(() => import("@/pages/progress-page"))
const ProfilePage = lazy(() => import("@/pages/profile-page"))
const NotFoundPage = lazy(() => import("@/pages/not-found-page"))
const AuthPage = lazy(() => import("@/pages/auth-page"))

/**
 * The refresh cookie is httpOnly, so on a cold load the client cannot tell
 * whether it has a session without asking the server. That makes this guard
 * asynchronous: children mount only once the answer is in, which keeps an
 * anonymous visitor from firing a page of doomed requests.
 */
function RequireAuth({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<"checking" | "authenticated" | "anonymous">(() =>
    getAccessToken() !== null ? "authenticated" : "checking",
  )

  useEffect(() => {
    if (status !== "checking") return
    let active = true
    void restoreSession().then((restored) => {
      if (active) setStatus(restored ? "authenticated" : "anonymous")
    })
    return () => {
      active = false
    }
  }, [status])

  if (status === "checking") {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-background">
        <Spinner className="size-6 text-muted-foreground" />
      </div>
    )
  }
  if (status === "anonymous") return <Navigate to="/login" replace />
  return children
}

/**
 * Bounces a signed-in visitor away from the login/register forms (e.g. after
 * hitting the browser back button post-login) to the app instead. Only checks
 * the in-memory access token — no need for RequireAuth's async cookie probe
 * here, since the common case (an anonymous visitor) must render the form
 * immediately rather than wait on a network round trip first.
 */
function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  if (getAccessToken() !== null) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route
          path="login"
          element={
            <RedirectIfAuthenticated>
              <AuthPage mode="login" />
            </RedirectIfAuthenticated>
          }
        />
        <Route
          path="register"
          element={
            <RedirectIfAuthenticated>
              <AuthPage mode="register" />
            </RedirectIfAuthenticated>
          }
        />
        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<HomePage />} />
          <Route path="food" element={<FoodPage />} />
          <Route path="workout" element={<WorkoutPage />} />
          <Route path="workout/plan" element={<WorkoutPlanPage />} />
          <Route path="coach" element={<CoachPage />} />
          <Route path="progress" element={<ProgressPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
