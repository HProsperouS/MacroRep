export type PipelineStepStatus = "done" | "running" | "waiting" | "failed"

export type PipelineStep = {
  id: string
  title: string
  detail: string
  status: PipelineStepStatus
}

export type ProposalStatus = "pending" | "applied" | "edited" | "rejected"
export type ProposalKind = "nutrition" | "training"

export type ProposalChange = {
  id: string
  label: string
  unit: "kcal" | "g" | "kg"
  before: number
  after: number
  /** Smallest allowed step when editing, e.g. 2.5 for barbell load. */
  step: number
}

export type Proposal = {
  id: string
  kind: ProposalKind
  headline: string
  changes: ProposalChange[]
  evidence: string[]
  reviewerNote: string
  status: ProposalStatus
  /** The changes exactly as proposed; `changes` holds the user's values once edited. */
  proposedChanges: ProposalChange[]
  /** ISO timestamp in UTC; null while pending. */
  decidedAt: string | null
}

export type CheckInStat = {
  label: string
  value: string
}

export type CheckIn = {
  id: string
  weekLabel: string
  rangeLabel: string
  /** "running" while proposals are generated in the background; "failed" if that went wrong. */
  status: "running" | "needs-review" | "reviewed" | "failed"
  /** Set when status is "failed". */
  failureReason: string | null
  summary: string
  stats: CheckInStat[]
  pipeline: PipelineStep[]
  proposals: Proposal[]
  suggestedQuestions: string[]
}

export type ProposalDecisionInput = {
  decision: "apply" | "reject"
  /** Edited values; omitted to apply as proposed. */
  changes?: { id: string; after: number }[]
}

export type CoachMessage = {
  id: string
  role: "user" | "coach"
  text: string
}
