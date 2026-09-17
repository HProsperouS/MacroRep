import { Check, Pencil, ShieldCheck, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { formatChangeValue, formatSigned } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { Proposal, ProposalStatus } from "@/types/coach"

const KIND_LABEL = { nutrition: "Nutrition", training: "Training" } as const

const STATUS_BADGE: Record<ProposalStatus, { label: string; className?: string; variant: "secondary" | "outline" | "destructive" }> = {
  pending: { label: "Proposal", variant: "outline" },
  applied: { label: "Applied", variant: "secondary", className: "bg-primary/12 text-primary" },
  edited: { label: "Applied with edits", variant: "secondary", className: "bg-primary/12 text-primary" },
  rejected: { label: "Rejected", variant: "destructive" },
}

type ProposalCardProps = {
  proposal: Proposal
  busy: boolean
  onApply: () => void
  onEdit: () => void
  onReject: () => void
}

export function ProposalCard({ proposal, busy, onApply, onEdit, onReject }: ProposalCardProps) {
  const badge = STATUS_BADGE[proposal.status]
  const decided = proposal.status !== "pending"

  return (
    <Card className={cn(proposal.status === "rejected" && "opacity-70")}>
      <CardHeader>
        <CardTitle>{KIND_LABEL[proposal.kind]}</CardTitle>
        <CardDescription className="text-foreground">{proposal.headline}</CardDescription>
        <CardAction>
          <Badge variant={badge.variant} className={badge.className}>
            {badge.label}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <table className="w-full text-sm">
          <caption className="sr-only">Proposed changes</caption>
          <thead>
            <tr className="text-left text-[11px] tracking-widest text-muted-foreground uppercase">
              <th scope="col" className="pb-2 font-semibold">Item</th>
              <th scope="col" className="pb-2 text-right font-semibold">Now</th>
              <th scope="col" className="pb-2 text-right font-semibold">New</th>
              <th scope="col" className="pb-2 text-right font-semibold">Change</th>
            </tr>
          </thead>
          <tbody>
            {proposal.changes.map((change) => {
              const delta = change.after - change.before
              return (
                <tr key={change.id} className="border-t">
                  <th scope="row" className="py-2.5 text-left font-normal">
                    {change.label}
                  </th>
                  <td className="py-2.5 text-right text-muted-foreground tabular-nums">{formatChangeValue(change.before, change.unit)}</td>
                  <td className="py-2.5 text-right font-medium tabular-nums">{formatChangeValue(change.after, change.unit)}</td>
                  <td className={cn("py-2.5 text-right tabular-nums", delta === 0 ? "text-muted-foreground" : "text-primary")}>
                    {delta === 0 ? "—" : formatSigned(delta)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        <div className="flex flex-col gap-2">
          <span className="text-[11px] font-semibold tracking-widest text-muted-foreground uppercase">Evidence</span>
          <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-muted-foreground">
            {proposal.evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <p className="flex items-start gap-2 rounded-lg bg-muted/50 px-3 py-2.5 text-sm">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <span>
            <span className="font-medium">Reviewer: </span>
            <span className="text-muted-foreground">{proposal.reviewerNote}</span>
          </span>
        </p>
      </CardContent>
      {decided ? null : (
        <CardFooter className="flex flex-wrap gap-2">
          <Button className="h-10 flex-1 sm:flex-none" onClick={onApply} disabled={busy}>
            <Check data-icon="inline-start" />
            Apply
          </Button>
          <Button variant="outline" className="h-10 flex-1 sm:flex-none" onClick={onEdit} disabled={busy}>
            <Pencil data-icon="inline-start" />
            Edit
          </Button>
          <Button variant="ghost" className="h-10 flex-1 sm:flex-none" onClick={onReject} disabled={busy}>
            <X data-icon="inline-start" />
            Reject
          </Button>
        </CardFooter>
      )}
    </Card>
  )
}
