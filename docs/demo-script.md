# Live demo script

About 12 minutes, one feature at a time. **Say** is what to say; **Do** is what to do while saying it. The AI's output can differ on every run, so when it's on screen, describe what's there rather than reciting fixed numbers.

## Before the demo

**30 minutes before you start, on the day:**

1. Rebuild the data: `docker compose down -v`, then `make dev`. The history is dated from the day it's seeded, so it has to be rebuilt the same day.
2. Check that `backend/.env` has `COACH_MODEL_PROVIDER=openai` and a valid key.
3. In a normal window, open http://localhost:5173, sign in to the demo account and stay on **Home**:
   - Email: `alex.yau@example.com`
   - Password: `nailong2`
4. In a private window, open the same address and stay on the sign-up page. Sign-up needs a new email each time, such as `demo1@example.com`.
5. Put a clear photo of a meal on the desktop.

**Don't run a check-in on the demo account beforehand.** Each user gets 5 a day, and a new one can't start while proposals are waiting for a decision. After a rehearsal, repeat step 1.

## 1. Opening (1 minute)

**Do:** Stay on the demo account's Home.

**Say:**

> Most fitness apps are good at one thing: recording. You log your food, you log your workouts, and then it's up to you to work out what the numbers mean.
>
> MacroRep closes that loop. It tracks nutrition and training in one place, and once a week a team of AI agents reviews your data and proposes changes to your plan.
>
> The important part is that the AI never changes anything by itself. You always make the final decision.
>
> Let me walk you through it, one feature at a time.

## 2. Sign-up and onboarding (1 minute)

**Do:** Switch to the private window.

**Say:**

> First, a new user. I'll create an account.

**Do:** Enter a name, email and password, then click **Create account**.

**Say:**

> Setup takes four short steps: about you, your goal, your training, and your daily targets.

**Do:** Fill in **About you**, **Your goal** and **Training**, moving to the next step each time. Stop on **Daily targets**.

**Say:**

> From those answers, MacroRep estimates starting calorie and macro targets. They're only a starting point: the user can change them now, and each weekly check-in adjusts them from what's actually logged.

**Do:** Finish setup. When the empty Home appears, close the private window.

## 3. Home (30 seconds)

**Do:** Go back to the demo account's **Home**.

**Say:**

> A new account starts empty, so I've switched to Alex, a demo user with four weeks of data.
>
> Home answers one question: what do I need to do today? Here's today's nutrition, today's planned workout, and a reminder that there's no weigh-in yet.

## 4. Logging food (1 minute)

**Do:** Click **Food**, choose **Lunch**, click **Search foods and dishes** and search for `chicken rice`.

**Say:**

> Now let's log lunch. The food library covers everyday foods and Singapore hawker dishes, so local meals are easy to find.

**Do:** Choose the dish, confirm the amount and click **Add to Lunch**.

**Say:**

> I pick an amount, and today's calories and macros update straight away.

## 5. Meal photos (1 minute)

**Do:** Click **Scan**, choose the photo from the desktop and wait for the **Check the photo estimate** dialog.

**Say:**

> Logging is where most people give up, so we've made it faster. I can take a photo of a meal, and AI estimates what's on the plate.

**Do:** Point at the result, then change an amount or remove an item.

**Say:**

> This is only an estimate, so nothing is saved yet. I can correct any item first, and it's logged only when I confirm. The photo goes to the model for analysis and isn't kept.

**Do:** Choose **Dinner** and click the **Log** button.

**If the estimate fails:** Say "The estimate is optional, so I can still log it by hand", then click **Quick add**.

## 6. Weighing in (30 seconds)

**Do:** Go back to **Home**, click the add button next to **No weigh-in today**, enter `77.9` and save.

**Say:**

> Weight goes up and down every day because of water and food. So MacroRep doesn't react to a single reading: it follows a smoothed trend, and that's the number the coach uses.

## 7. Logging a workout (1 minute 30 seconds)

**Do:** Click **Workout**.

**Say:**

> Alex's weekly plan has a Push day scheduled today, so I can start it with one tap.

**Do:** Click **Start planned workout**.

**Say:**

> The sets are already laid out from the routine. For each set I record the weight, reps and how hard it felt, using a rating called RPE.

**Do:** On the first working set of Barbell Bench Press, enter the weight, reps and RPE, then complete the set so the rest timer appears.

**Say:**

> When I finish a set, the rest timer starts on its own.

**Do:** Click **Skip**, quickly complete one or two more sets and click **Finish workout**. If **Finish with sets left?** appears, confirm that you want to finish.

**Say:**

> In a real session I'd complete every set, but I'll finish here. The app saves the workout and gives me a summary of the session.

## 8. Workout plan (30 seconds)

**Do:** Go back to **Workout** and open the weekly plan page (`/workout/plan`).

**Say:**

> Routines are reusable. I choose the exercises, sets, targets and rest times, then place them on the days of the week. These targets are also what the Workout agent will adjust later on.

## 9. Progress (1 minute)

**Do:** Click **Progress** and keep the **1M** range.

**Say:**

> Progress brings the month together. Here's Alex's trend weight, how many days were logged, workouts done, training volume and average effort.

**Do:** Point at the **Weight** chart.

**Say:**

> Alex's goal is to lose half a kilo a week, but the trend is falling more slowly than that, even though most days were logged and close to target. A chart can show you that. It can't tell you what to do next.
>
> That's the job of the weekly check-in.

## 10. Weekly check-in (3 minutes, the main feature)

**Do:** Click **Coach**, then **Start check-in**.

**Say:**

> When I start a check-in, the app first makes sure there's enough data to judge: food on at least four of the last seven days, and at least two weigh-ins.
>
> It then freezes the week into a snapshot. The agents only see those figures, with no name or email, so no personal details reach the model.

**Do:** Point at the progress steps while it runs. A result usually takes 10 to 20 seconds.

**Say:**

> Three agents work on it. The Nutrition agent looks only at food and weight. The Workout agent looks only at training. Then a Reviewer reads both proposals together, because two sensible ideas can still clash.
>
> After that, fixed rules check every number against product limits, so a bad model output can't turn into a bad plan.

**Do:** When the status changes to **Needs review**, point at the summary, then at the **Now / New / Change** columns of the proposal.

**Say:**

> Here's the result. Each change shows the current value, the new value, and the difference.

**Do:** Point at **Evidence**.

**Say:**

> And every proposal shows its evidence, so I can see why it was made. Here it cites Alex's own numbers.

Read out one real piece of evidence from the screen. The data was built so that the lat pulldown is getting easier, while the squat's RPE is rising with no gain in strength.

**Do:** Open **How this check-in was made**, show the Reviewer step, then show the **Reviewer** note on the proposal.

**If the Reviewer held the calorie change back, say:**

> This is my favourite part. The Nutrition agent wanted to cut calories, but the Workout agent wanted to increase training. The Reviewer saw that doing both at once could hurt recovery, so it held the calorie cut back and explained why. That's what a multi-agent design gives us: one agent checking the others.

**If both proposals were kept, say:**

> The Reviewer looked at both proposals together, found no conflict, and kept them. It can hold a proposal back, but it can never add a change of its own.

## 11. Coach Chat (1 minute)

**Do:** Under **Ask the coach**, click a suggested question or type:

```text
Why did you suggest this change?
```

**Say:**

> If I'm not sure about a proposal, I can just ask. The answers use only my logged data and this check-in.

**Do:** If the proposal includes the squat, type the line below. Otherwise, use another exercise from the screen.

```text
Can we lower the squat by only 2.5 kg instead?
```

**Say:**

> I can also talk it through. The coach revises the proposal, and the revision goes back through the same checks as the original.

## 12. The user decides (1 minute)

**Do:** Point at the **Apply**, **Edit** and **Reject** buttons.

**Say:**

> Up to this point, nothing in Alex's plan has changed. Everything you've seen is only a proposal. I can apply it, edit the values myself, or reject it.

**Do:** Click **Apply**. Open `/workout/plan` and show the changed target.

**Say:**

> I'll apply it, and now the routine has the new target. Next week's check-in will judge how that went, and that's the loop: track, review, decide, and repeat.

If you applied a calorie proposal instead, open **Food** and point at the new daily target.

## 13. Closing (30 seconds)

**Say:**

> So that's MacroRep: nutrition and training tracked in one place, specialised agents that check each other, fixed rules around every number, and the user in control of every change.
>
> Thank you. We'd be happy to take your questions.

## If something goes wrong

| What happened | Say | Do |
|---|---|---|
| The photo estimate fails | "The estimate is optional, so I can still log it by hand." | Use **Quick add** |
| The check-in fails or times out | "Live AI calls can fail, and the app says so instead of guessing." | Click **Try again**; if it fails again, play the recording |
| The check-in says there isn't enough data | "The app refuses to judge a week without enough data." | The data wasn't rebuilt today; play the recording |
| Chat doesn't answer | "The coach would rather say nothing than make something up." | Skip to section 12 |
| The app or Docker won't open | "Let me switch to a recording of the same flow." | Play the recording |

## If time is short

With only 6 minutes, keep sections 1, 5, 10, 11, 12 and 13, and cut section 9 down to one sentence.

## Questions you may be asked

**Why use several agents? Wouldn't one be enough?**

> Each agent sees only the data it needs, and the Reviewer gives us an independent check across both. A single agent would have nothing checking its reasoning.

**What happens if the AI gets something wrong?**

> Model output has to fit a strict schema, and fixed rules check every value. The change is checked again when it's applied, and nothing happens without the user's approval.

**Is personal data sent to OpenAI?**

> Check-ins send weekly figures only, with no name or email. Meal photos go to the model for analysis and aren't kept.

**Is this medical advice?**

> No. The coach turns down medical questions and stays within fixed limits, such as a minimum calorie target.

**Is it deployed?**

> Not yet. This demo runs locally, and the AWS deployment is documented as a design.
