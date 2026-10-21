import { lazy, Suspense, useEffect, useState, type ReactNode } from "react"
import { Navigate, Route, Routes } from "react-router-dom"

import { restoreSession } from "@/api/client"
import { AppShell } from "@/components/layout/app-shell"
import { Spinner } from "@/components/ui/spinner"
import { useProfile } from "@/hooks/use-profile"
import { getAccessToken } from "@/lib/auth"

const HomePage = lazy(() => import("@/pages/home-page"))
const FoodPage = lazy(() => import("@/pages/food-page"))
const WorkoutPage = lazy(() => import("@/pages/workout-page"))
const WorkoutHistoryPage = lazy(() => import("@/pages/workout-history-page"))
const WorkoutPlanPage = lazy(() => import("@/pages/workout-plan-page"))
const CoachPage = lazy(() => import("@/pages/coach-page"))
const ProgressPage = lazy(() => import("@/pages/progress-page"))
const ProfilePage = lazy(() => import("@/pages/profile-page"))
const NotFoundPage = lazy(() => import("@/pages/not-found-page"))
const AuthPage = lazy(() => import("@/pages/auth-page"))
const OnboardingPage = lazy(() => import("@/pages/onboarding-page"))

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

  if (status === "checking") return <FullPageSpinner />
  if (status === "anonymous") return <Navigate to="/login" replace />
  return children
}

function FullPageSpinner() {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background">
      <Spinner className="size-6 text-muted-foreground" />
    </div>
  )
}

/**
 * Sends a new account through the sign-up guide before the app. If the profile can't be
 * loaded, the app opens anyway: its pages show their own errors, and nobody is locked out.
 */
function RequireOnboarded({ children }: { children: ReactNode }) {
  const profile = useProfile()
  // Only before the first answer: a refetch after a failure is pending again, and hiding the
  // app then would unmount the pages whose own queries started that refetch.
  if (profile.isPending && profile.errorUpdateCount === 0) return <FullPageSpinner />
  if (profile.data?.onboarded === false) return <Navigate to="/welcome" replace />
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
          path="welcome"
          element={
            <RequireAuth>
              <OnboardingPage />
            </RequireAuth>
          }
        />
        <Route
          element={
            <RequireAuth>
              <RequireOnboarded>
                <AppShell />
              </RequireOnboarded>
            </RequireAuth>
          }
        >
          <Route index element={<HomePage />} />
          <Route path="food" element={<FoodPage />} />
          <Route path="workout" element={<WorkoutPage />} />
          <Route path="workout/history" element={<WorkoutHistoryPage />} />
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
