import { Sparkles } from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useCurrentCheckIn } from "@/hooks/use-coach"

type CheckInBannerProps = {
  dismissed: boolean
  onDismiss: () => void
}

/** Shown only when a check-in is waiting for review; errors stay on the Coach page. */
export function CheckInBanner({ dismissed, onDismiss }: CheckInBannerProps) {
  const checkIn = useCurrentCheckIn()
  const pending = checkIn.data?.proposals.filter((proposal) => proposal.status === "pending").length ?? 0

  if (dismissed || !checkIn.data || pending === 0) return null

  return (
    <Card className="bg-primary/5 ring-primary/35">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[11px] font-semibold tracking-widest text-primary uppercase">
          <Sparkles className="size-4" aria-hidden />
          Weekly check-in ready
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-base leading-snug font-semibold">
          Your coach reviewed 7 days of food, weight and training data and has {pending} proposed change{pending === 1 ? "" : "s"}.
        </p>
      </CardContent>
      <CardFooter className="gap-2 border-t-0 bg-transparent">
        <Button className="h-10 flex-1" asChild>
          <Link to="/coach">Review changes</Link>
        </Button>
        <Button variant="outline" className="h-10" onClick={onDismiss}>
          Later
        </Button>
      </CardFooter>
    </Card>
  )
}
