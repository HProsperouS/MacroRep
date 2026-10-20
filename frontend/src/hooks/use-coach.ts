import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef } from "react"

import { coachApi } from "@/api/coach-api"
import { createRequestId } from "@/api/client"
import { coachKeys, foodKeys, progressKeys, workoutKeys } from "@/api/query-keys"
import type { CheckIn, CoachMessage, Proposal, ProposalDecisionInput } from "@/types/coach"

/** How often to look again while a check-in is being generated in the background. */
export const CHECK_IN_POLL_MS = 2_000

export function useCurrentCheckIn() {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: coachKeys.current(),
    queryFn: ({ signal }) => coachApi.getCurrentCheckIn(signal),
    refetchInterval: (query) => (query.state.data?.status === "running" ? CHECK_IN_POLL_MS : false),
  })

  // A check-in joins the Progress history only once it's finished, so refresh it then.
  const status = query.data?.status
  const previous = useRef(status)
  useEffect(() => {
    if (previous.current === "running" && status !== undefined && status !== "running") {
      void queryClient.invalidateQueries({ queryKey: progressKeys.all })
    }
    previous.current = status
  }, [status, queryClient])

  return query
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
      // Running for now; useCurrentCheckIn polls it and refreshes Progress when it's done.
      queryClient.setQueryData(coachKeys.current(), checkIn)
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
      if (proposal.kind === "nutrition") {
        // Also refreshes the target history, which is keyed under the targets.
        void queryClient.invalidateQueries({ queryKey: foodKeys.targets() })
        void queryClient.invalidateQueries({ queryKey: [...foodKeys.all, "daily-calories"] })
        // Progress and Home measure intake against the target.
        void queryClient.invalidateQueries({ queryKey: progressKeys.all })
      } else void queryClient.invalidateQueries({ queryKey: workoutKeys.all })
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  })
}

export function useCoachMessages(checkInId: string) {
  return useQuery({
    queryKey: coachKeys.messages(checkInId),
    queryFn: ({ signal }) => coachApi.listMessages(checkInId, signal),
  })
}

/** The server keeps the question and the answer only once there is an answer, so both join the conversation then. */
export function useAskCoach(checkInId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (text: string) => coachApi.askCoach(checkInId, text),
    onSuccess: (reply, text) =>
      queryClient.setQueryData<CoachMessage[]>(coachKeys.messages(checkInId), (old) => [
        ...(old ?? []),
        { id: createRequestId(), role: "user", text },
        reply,
      ]),
    // The browser may have given up on an answer the server still saved.
    onError: () => queryClient.invalidateQueries({ queryKey: coachKeys.messages(checkInId) }),
  })
}
