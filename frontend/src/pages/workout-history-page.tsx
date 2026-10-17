import { History } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { PageHeader } from "@/components/layout/page-header"
import { QueryError } from "@/components/layout/query-error"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { HistoryRow } from "@/components/workout/history-row"
import { useWorkoutHistory } from "@/hooks/use-workout"

export default function WorkoutHistoryPage() {
  const navigate = useNavigate()
  const history = useWorkoutHistory()
  const workouts = history.data?.pages.flat()

  return (
    <>
      <PageHeader
        eyebrow="Workout"
        title="History"
        actions={
          <Button variant="outline" className="h-10" onClick={() => navigate("/workout")}>
            Back to workout
          </Button>
        }
      />

      {history.isError && !workouts ? (
        <QueryError title="Couldn’t load your workouts" error={history.error} onRetry={() => void history.refetch()} retrying={history.isFetching} />
      ) : !workouts ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading workouts">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-20 w-full" />
          ))}
        </div>
      ) : workouts.length === 0 ? (
        <Empty className="border py-10">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <History />
            </EmptyMedia>
            <EmptyTitle>No workouts yet</EmptyTitle>
            <EmptyDescription>Finish a workout and it will show up here.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <>
          <Card className="gap-0 overflow-hidden py-0">
            <ul className="divide-y">
              {workouts.map((workout) => (
                <HistoryRow key={workout.id} workout={workout} />
              ))}
            </ul>
          </Card>
          {history.isFetchNextPageError ? (
            <QueryError title="Couldn’t load more workouts" error={history.error} onRetry={() => void history.fetchNextPage()} retrying={history.isFetchingNextPage} />
          ) : null}
          {history.hasNextPage ? (
            <Button variant="outline" className="h-10 self-center" disabled={history.isFetchingNextPage} onClick={() => void history.fetchNextPage()}>
              {history.isFetchingNextPage ? <Spinner data-icon="inline-start" /> : null}
              Load more
            </Button>
          ) : null}
        </>
      )}
    </>
  )
}
