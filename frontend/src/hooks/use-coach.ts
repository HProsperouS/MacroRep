import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useRef } from "react"

import { coachApi } from "@/api/coach-api"
import { createRequestId } from "@/api/client"
import { coachKeys, foodKeys, progressKeys, workoutKeys } from "@/api/query-keys"
import type { CheckIn, Proposal, ProposalDecisionInput } from "@/types/coach"

export function useCurrentCheckIn() {
  return useQuery({
    queryKey: coachKeys.current(),
    queryFn: ({ signal }) => coachApi.getCurrentCheckIn(signal),
  })
}

/**
 * Starts a new weekly check-in. One idempotency key is kept per attempt until it
 * succeeds, so retrying after a timeout or dropped connection (when the first
 * request may have gone through) returns that check-in rather than creating a second.
 */
export function useStartCheckIn() {
  const queryClient = useQueryClient()
  const idempotencyKey = useRef<string | null>(null)

  return useMutation({
    mutationFn: () => {
      idempotencyKey.current ??= createRequestId()
      return coachApi.startCheckIn(idempotencyKey.current)
    },
    onSuccess: (checkIn) => {
      idempotencyKey.current = null
      queryClient.setQueryData(coachKeys.current(), checkIn)
      void queryClient.invalidateQueries({ queryKey: progressKeys.all })
    },
  })
}

type DecisionVariables = ProposalDecisionInput & { proposal: Proposal }

/** Applies or rejects a proposal. The card updates immediately and rolls back on error. */
export function useDecideProposal(checkInId: string) {
  const queryClient = useQueryClient()
  const queryKey = coachKeys.current()

  return useMutation({
    mutationFn: ({ proposal, decision, changes }: DecisionVariables) => coachApi.decideProposal(checkInId, proposal.id, { decision, changes }),
    onMutate: async ({ proposal, decision, changes }) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<CheckIn | null>(queryKey)
      const edited = changes?.some((change) => proposal.changes.find((c) => c.id === change.id)?.after !== change.after) ?? false
      const status: Proposal["status"] = decision === "reject" ? "rejected" : edited ? "edited" : "applied"
      queryClient.setQueryData<CheckIn | null>(queryKey, (old) =>
        old ? { ...old, proposals: old.proposals.map((p) => (p.id === proposal.id ? { ...p, status } : p)) } : old,
      )
      return { previous }
    },
    onError: (_error, _variables, context) => {
      queryClient.setQueryData(queryKey, context?.previous)
    },
    onSuccess: (_data, { proposal, decision }) => {
      if (decision !== "apply") return
      if (proposal.kind === "nutrition") void queryClient.invalidateQueries({ queryKey: foodKeys.targets() })
      else void queryClient.invalidateQueries({ queryKey: workoutKeys.all })
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  })
}

export function useAskCoach(checkInId: string) {
  return useMutation({
    mutationFn: (text: string) => coachApi.askCoach(checkInId, text),
  })
}
