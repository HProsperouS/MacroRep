import { apiClient } from "@/api/client"
import type { CheckIn, CoachMessage, Proposal, ProposalDecisionInput } from "@/types/coach"

export const coachApi = {
  /** The latest weekly check-in, or null before the first one is generated. */
  async getCurrentCheckIn(signal?: AbortSignal) {
    const { data } = await apiClient.get<CheckIn | null>("/coach/check-ins/current", { signal })
    return data
  },

  /**
   * Reviews the last 7 days and drafts proposals. Sending the same key again returns
   * the check-in that key already created instead of making a second one.
   */
  async startCheckIn(idempotencyKey: string) {
    const { data } = await apiClient.post<CheckIn>("/coach/check-ins", null, {
      headers: { "Idempotency-Key": idempotencyKey },
    })
    return data
  },

  async decideProposal(checkInId: string, proposalId: string, input: ProposalDecisionInput) {
    const { data } = await apiClient.post<Proposal>(
      `/coach/check-ins/${encodeURIComponent(checkInId)}/proposals/${encodeURIComponent(proposalId)}/decision`,
      input,
    )
    return data
  },

  async askCoach(checkInId: string, text: string) {
    const { data } = await apiClient.post<CoachMessage>(`/coach/check-ins/${encodeURIComponent(checkInId)}/messages`, { text })
    return data
  },
}
