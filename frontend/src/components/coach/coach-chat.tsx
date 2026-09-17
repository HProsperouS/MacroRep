import { ArrowUp, Sparkles } from "lucide-react"
import { useState, type FormEvent } from "react"

import { apiErrorMessage, createRequestId } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupTextarea } from "@/components/ui/input-group"
import { Spinner } from "@/components/ui/spinner"
import { useAskCoach } from "@/hooks/use-coach"
import { cn } from "@/lib/utils"
import type { CoachMessage } from "@/types/coach"

const MAX_LENGTH = 500

type CoachChatProps = {
  checkInId: string
  suggestions: string[]
  className?: string
}

/** Constrained Q&A: answers use only the user's logged data and this check-in. */
export function CoachChat({ checkInId, suggestions, className }: CoachChatProps) {
  const [messages, setMessages] = useState<CoachMessage[]>([])
  const [draft, setDraft] = useState("")
  const [failed, setFailed] = useState<string | null>(null)
  const ask = useAskCoach(checkInId)

  function send(text: string) {
    const question = text.trim()
    if (!question || ask.isPending) return
    setFailed(null)
    setMessages((prev) => [...prev, { id: createRequestId(), role: "user", text: question }])
    setDraft("")
    ask.mutate(question, {
      onSuccess: (reply) => setMessages((prev) => [...prev, reply]),
      onError: (error) => setFailed(apiErrorMessage(error)),
    })
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    send(draft)
  }

  const lastQuestion = [...messages].reverse().find((message) => message.role === "user")?.text

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Ask the coach</CardTitle>
        <CardDescription>Answers use only your logged data and this check-in.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <ol className="flex max-h-96 flex-col gap-3 overflow-y-auto" aria-live="polite" aria-label="Conversation">
          <li className="flex gap-2">
            <Sparkles className="mt-1 size-4 shrink-0 text-primary" aria-hidden />
            <p className="rounded-lg bg-muted/60 px-3 py-2 text-sm">
              Want me to explain the calorie change, or adjust how the carbs are spread across training and rest days?
            </p>
          </li>
          {messages.map((message) => (
            <li key={message.id} className={cn("flex gap-2", message.role === "user" && "justify-end")}>
              {message.role === "coach" ? <Sparkles className="mt-1 size-4 shrink-0 text-primary" aria-hidden /> : null}
              <p
                className={cn(
                  "max-w-[85%] rounded-lg px-3 py-2 text-sm break-words whitespace-pre-wrap",
                  message.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted/60",
                )}
              >
                <span className="sr-only">{message.role === "user" ? "You: " : "Coach: "}</span>
                {message.text}
              </p>
            </li>
          ))}
          {ask.isPending ? (
            <li className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner /> Coach is checking your data…
            </li>
          ) : null}
        </ol>

        {failed ? (
          <p className="flex flex-wrap items-center gap-2 text-sm text-destructive" role="alert">
            Couldn’t get an answer. {failed}
            {lastQuestion ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setMessages((prev) => prev.slice(0, -1))
                  send(lastQuestion)
                }}
              >
                Retry
              </Button>
            ) : null}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {suggestions.map((suggestion) => (
            <Button key={suggestion} variant="outline" size="sm" className="h-8 rounded-full" onClick={() => send(suggestion)} disabled={ask.isPending}>
              {suggestion}
            </Button>
          ))}
        </div>

        <form onSubmit={submit}>
          <InputGroup>
            <InputGroupTextarea
              aria-label="Ask the coach"
              placeholder="Ask about this check-in"
              value={draft}
              maxLength={MAX_LENGTH}
              rows={2}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault()
                  send(draft)
                }
              }}
            />
            <InputGroupAddon align="block-end">
              <span className="text-xs text-muted-foreground tabular-nums">
                {draft.length}/{MAX_LENGTH}
              </span>
              <InputGroupButton type="submit" variant="default" size="icon-sm" className="ml-auto" aria-label="Send question" disabled={!draft.trim() || ask.isPending}>
                <ArrowUp />
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </form>
      </CardContent>
    </Card>
  )
}
