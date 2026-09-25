import { CheckCheck, History, Sparkles } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { CoachChat } from "@/components/coach/coach-chat"
import { EditProposalForm } from "@/components/coach/edit-proposal-form"
import { PipelineSteps } from "@/components/coach/pipeline-steps"
import { ProposalCard } from "@/components/coach/proposal-card"
import { PageHeader } from "@/components/layout/page-header"
import { QueryError } from "@/components/layout/query-error"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { useCurrentCheckIn, useDecideProposal, useStartCheckIn } from "@/hooks/use-coach"
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/use-media-query"
import type { CheckIn, Proposal, ProposalDecisionInput } from "@/types/coach"

export default function CoachPage() {
  const checkIn = useCurrentCheckIn()

  if (checkIn.isPending) return <CoachSkeleton />

  if (checkIn.isError) {
    return (
      <>
        <PageHeader title="Weekly check-in" />
        <QueryError title="Couldn’t load your check-in" error={checkIn.error} onRetry={() => void checkIn.refetch()} retrying={checkIn.isFetching} />
      </>
    )
  }

  if (!checkIn.data) {
    return (
      <>
        <PageHeader title="Weekly check-in" />
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Sparkles />
            </EmptyMedia>
            <EmptyTitle>No check-in yet</EmptyTitle>
            <EmptyDescription>A check-in reviews your last 7 days. It needs food logged on at least 4 of those days and at least 2 weigh-ins.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent className="flex-row justify-center gap-2">
            <StartCheckInButton label="Start check-in" />
            <Button variant="outline" className="h-10" asChild>
              <Link to="/food">Log food</Link>
            </Button>
          </EmptyContent>
        </Empty>
      </>
    )
  }

  return <CheckInView checkIn={checkIn.data} />
}

type Editing = { proposal: Proposal; layout: OverlayLayout } | null

function CheckInView({ checkIn }: { checkIn: CheckIn }) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const decide = useDecideProposal(checkIn.id)
  const [editing, setEditing] = useState<Editing>(null)

  const pending = checkIn.proposals.filter((proposal) => proposal.status === "pending")
  const busyId = decide.isPending ? decide.variables?.proposal.id : undefined

  function run(proposal: Proposal, input: ProposalDecisionInput, onDone?: () => void) {
    decide.mutate(
      { proposal, ...input },
      {
        onSuccess: () => {
          onDone?.()
          toast.success(input.decision === "reject" ? "Proposal rejected" : "Change applied", {
            description: input.decision === "reject" ? "Your plan stays as it is." : proposal.kind === "nutrition" ? "Your daily targets are updated." : "Your next sessions use the new loads.",
          })
        },
        onError: (error) => toast.error("Couldn’t save your decision", { description: apiErrorMessage(error) }),
      },
    )
  }

  async function applyAll() {
    try {
      // Sequential so the reviewer sees each decision in order.
      for (const proposal of pending) {
        await decide.mutateAsync({ proposal, decision: "apply" })
      }
      toast.success("All changes applied", { description: "Targets and training loads are updated." })
    } catch (error) {
      toast.error("Some changes weren’t applied", { description: apiErrorMessage(error) })
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={`${checkIn.weekLabel} · ${checkIn.rangeLabel}`}
        title="Weekly check-in"
        actions={
          <>
            {pending.length > 0 ? (
              <Badge variant="outline" className="hidden text-carbs sm:inline-flex">
                Needs review
              </Badge>
            ) : (
              <Badge className="hidden bg-primary/12 text-primary sm:inline-flex">Reviewed</Badge>
            )}
            <Button variant="outline" className="hidden h-10 md:inline-flex" asChild>
              <Link to="/progress">
                <History data-icon="inline-start" />
                History
              </Link>
            </Button>
            {pending.length > 0 ? (
              <Button className="h-10" onClick={() => void applyAll()} disabled={decide.isPending}>
                <CheckCheck data-icon="inline-start" />
                Apply all
              </Button>
            ) : (
              <StartCheckInButton label="New check-in" />
            )}
          </>
        }
      />

      <PipelineSteps steps={checkIn.pipeline} />

      <div className="grid items-start gap-4 lg:grid-cols-12 lg:gap-6">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-8">
          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-base leading-relaxed">{checkIn.summary}</p>
              <dl className="grid grid-cols-2 gap-3 border-t pt-4 sm:grid-cols-3 xl:grid-cols-5">
                {checkIn.stats.map((stat) => (
                  <div key={stat.label} className="flex min-w-0 flex-col gap-1">
                    <dt className="text-[11px] font-semibold tracking-widest text-muted-foreground uppercase">{stat.label}</dt>
                    <dd className="font-display text-2xl leading-none font-semibold">{stat.value}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>

          {checkIn.proposals.map((proposal) => (
            <ProposalCard
              key={proposal.id}
              proposal={proposal}
              busy={busyId === proposal.id}
              onApply={() => run(proposal, { decision: "apply" })}
              onReject={() => run(proposal, { decision: "reject" })}
              onEdit={() => setEditing({ proposal, layout: isDesktop ? "dialog" : "drawer" })}
            />
          ))}
        </div>

        <CoachChat checkInId={checkIn.id} suggestions={checkIn.suggestedQuestions} className="lg:sticky lg:top-7 lg:col-span-4" />
      </div>

      <ResponsiveOverlay
        open={editing !== null}
        onOpenChange={(open) => (open ? undefined : setEditing(null))}
        layout={editing?.layout ?? "dialog"}
        title="Edit proposal"
        description="Adjust the values, then apply. The reviewer’s weekly limits still apply."
      >
        {editing ? (
          <EditProposalForm
            key={editing.proposal.id}
            proposal={editing.proposal}
            submitting={decide.isPending}
            onCancel={() => setEditing(null)}
            onSubmit={(changes) => run(editing.proposal, { decision: "apply", changes }, () => setEditing(null))}
          />
        ) : null}
      </ResponsiveOverlay>
    </>
  )
}

function StartCheckInButton({ label }: { label: string }) {
  const start = useStartCheckIn()

  function run() {
    start.mutate(undefined, {
      onSuccess: (checkIn) =>
        toast.success(`${checkIn.weekLabel} check-in ready`, {
          description: checkIn.proposals.length > 0 ? "Review the proposed changes below." : "No changes needed this week.",
        }),
      onError: (error) => toast.error("Couldn’t start a check-in", { description: apiErrorMessage(error) }),
    })
  }

  return (
    <Button className="h-10" onClick={run} disabled={start.isPending}>
      {start.isPending ? <Spinner data-icon="inline-start" /> : <Sparkles data-icon="inline-start" />}
      {label}
    </Button>
  )
}

function CoachSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading check-in">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-8 w-56" />
      </div>
      <Skeleton className="h-36 w-full" />
      <div className="grid gap-4 lg:grid-cols-12 lg:gap-6">
        <div className="flex flex-col gap-4 lg:col-span-8">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
        <Skeleton className="h-96 lg:col-span-4" />
      </div>
    </div>
  )
}
