import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { coachApi } from "@/api/coach-api"
import { coachKeys, foodKeys, workoutKeys } from "@/api/query-keys"
import type { CheckIn, Proposal, ProposalDecisionInput } from "@/types/coach"

export function useCurrentCheckIn() {
  return useQuery({
    queryKey: coachKeys.current(),
    queryFn: ({ signal }) => coachApi.getCurrentCheckIn(signal),
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
