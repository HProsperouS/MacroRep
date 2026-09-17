import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { PageHeader } from "@/components/layout/page-header"
import { QueryError } from "@/components/layout/query-error"
import { ProfileForm } from "@/components/profile/profile-form"
import { TargetsForm } from "@/components/profile/targets-form"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useNutritionTargets } from "@/hooks/use-food-log"
import { useProfile, useUpdateProfile, useUpdateTargets } from "@/hooks/use-profile"

export default function ProfilePage() {
  const profile = useProfile()
  const targets = useNutritionTargets()
  const updateProfile = useUpdateProfile()
  const updateTargets = useUpdateTargets()

  return (
    <>
      <PageHeader eyebrow="Settings" title="Profile" />

      <div className="grid items-start gap-4 lg:grid-cols-12 lg:gap-6">
        <Card className="lg:col-span-7">
          <CardHeader>
            <CardTitle>About you</CardTitle>
            <CardDescription>Units are metric.</CardDescription>
          </CardHeader>
          <CardContent>
            {profile.isError ? (
              <QueryError title="Couldn’t load your profile" error={profile.error} onRetry={() => void profile.refetch()} retrying={profile.isFetching} />
            ) : profile.data ? (
              <ProfileForm
                // Remount with fresh defaults after a save so "unsaved changes" resets.
                key={profile.dataUpdatedAt}
                profile={profile.data}
                submitting={updateProfile.isPending}
                onSubmit={(input) =>
                  updateProfile.mutate(input, {
                    onSuccess: () => toast.success("Profile saved"),
                    onError: (error) => toast.error("Couldn’t save your profile", { description: apiErrorMessage(error) }),
                  })
                }
              />
            ) : (
              <FormSkeleton rows={3} />
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-5">
          <CardHeader>
            <CardTitle>Daily targets</CardTitle>
            <CardDescription>Your weekly check-in may propose changes to these.</CardDescription>
          </CardHeader>
          <CardContent>
            {targets.isError ? (
              <QueryError title="Couldn’t load your targets" error={targets.error} onRetry={() => void targets.refetch()} retrying={targets.isFetching} />
            ) : targets.data ? (
              <TargetsForm
                key={targets.dataUpdatedAt}
                targets={targets.data}
                submitting={updateTargets.isPending}
                onSubmit={(input) =>
                  updateTargets.mutate(input, {
                    onSuccess: () => toast.success("Targets saved", { description: "Food and Home now use the new numbers." }),
                    onError: (error) => toast.error("Couldn’t save your targets", { description: apiErrorMessage(error) }),
                  })
                }
              />
            ) : (
              <FormSkeleton rows={2} />
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}

function FormSkeleton({ rows }: { rows: number }) {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex flex-col gap-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
      <Skeleton className="ml-auto h-10 w-32" />
    </div>
  )
}
