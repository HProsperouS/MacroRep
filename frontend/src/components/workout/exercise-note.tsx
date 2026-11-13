import { PencilLine, Plus } from "lucide-react"
import { useState, type KeyboardEvent } from "react"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useSaveExerciseNote } from "@/hooks/use-workout"
import type { SessionAction, SessionExercise } from "@/lib/workout-session"

export const MAX_NOTE_LENGTH = 500

type ExerciseNoteProps = {
  exercise: Pick<SessionExercise, "exerciseId" | "name" | "userNote">
  dispatch: (action: SessionAction) => void
}

/** The lifter's own note on an exercise (cues, machine settings). Saved to the server as soon as
 *  it's edited, so it's there the next time the exercise comes up, even if this workout is discarded. */
export function ExerciseNote({ exercise, dispatch }: ExerciseNoteProps) {
  const saved = exercise.userNote ?? ""
  const [draft, setDraft] = useState<string | null>(null)
  const save = useSaveExerciseNote()

  function commit() {
    if (draft === null) return
    const body = draft.trim()
    setDraft(null)
    if (body === saved.trim()) return
    dispatch({ type: "edit-note", exerciseId: exercise.exerciseId, value: body })
    save.mutate(
      { exerciseId: exercise.exerciseId, body },
      {
        onError: (error) =>
          toast.error("Couldn’t save your note", {
            description: apiErrorMessage(error),
            action: { label: "Retry", onClick: () => save.mutate({ exerciseId: exercise.exerciseId, body }) },
          }),
      },
    )
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Escape") {
      event.preventDefault()
      setDraft(null)
    } else if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      commit()
    }
  }

  if (draft !== null) {
    return (
      <div className="flex flex-col gap-1.5">
        <Textarea
          autoFocus
          aria-label={`Note for ${exercise.name}`}
          placeholder="Seat height, grip, cues… shows up every time you do this exercise."
          maxLength={MAX_NOTE_LENGTH}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={onKeyDown}
          className="min-h-20"
        />
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="tabular-nums">
            {draft.length}/{MAX_NOTE_LENGTH}
          </span>
          {/* Saving happens on blur, so this button only needs to take focus away. */}
          <Button size="sm" className="h-9 px-3" onClick={commit}>
            Done
          </Button>
        </div>
      </div>
    )
  }

  if (!saved) {
    return (
      <Button variant="ghost" size="sm" className="h-9 self-start px-2 text-muted-foreground" onClick={() => setDraft("")}>
        <Plus data-icon="inline-start" />
        Add note
      </Button>
    )
  }

  return (
    <button
      type="button"
      className="flex w-full items-start gap-2 rounded-lg border border-dashed bg-muted/40 px-3 py-2 text-left text-sm whitespace-pre-wrap transition-colors hover:bg-muted"
      aria-label={`Edit note for ${exercise.name}`}
      onClick={() => setDraft(saved)}
    >
      <PencilLine className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span className="min-w-0 flex-1 break-words">{saved}</span>
    </button>
  )
}
