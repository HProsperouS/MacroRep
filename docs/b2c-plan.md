# MacroRep for the busy lifter: a coach in your pocket

**Status:** proposal, 2026-11-10. Not yet agreed by the team.
**Relationship to [plan.md](plan.md):** keeps every feature already built, narrows who MacroRep is *for*, and adds the features that person needs. Nothing here replaces the course deliverables; it changes the story the project tells and adds one new capability (a daily coach) on top of the weekly one.

## 1. The reframe in one paragraph

Today MacroRep is described as a tracker for "beginner-to-intermediate gym users" with a weekly AI check-in. That is everyone, so it is no one. The reframe: **MacroRep is for people with a full-time job who lift two to four times a week and don't have a coach.** Their problem isn't recording what they did. It's knowing **what to do today**, when they slept badly, their back feels tight, or they only have 30 minutes. MacroRep already answers "what should change next week". The plan adds "what should I do today", with the same rules: the user decides, every number is bounded, and the coach never pretends to be a doctor.

## 2. Who it's for

**Primary persona: the busy lifter.**

- Works full time, trains 2–4 times a week, sessions of 30–60 minutes.
- Has been lifting for at least a few months and follows a routine, but nobody tells them how to adjust it.
- Sleep, stress and time vary week to week. The plan in the app doesn't vary with them.
- Gets the ordinary aches of training: a tight lower back, sore knees after a heavy leg day. These are not injuries that need a physio.
- Wants to look and feel better (lose fat, or build some muscle) without making nutrition a second job.
- Won't pay for a personal trainer, or tried one and stopped.

**Not the target (we don't design for them, though they can still use the app):**

- Competitive powerlifters and physique athletes, who want fine-grained programming control.
- Complete beginners who need to be taught the exercises themselves (form videos, exercise selection).
- Anyone with a diagnosed injury or medical condition who needs rehabilitation.

## 3. The pain point, and why we believe it

**Main bet: "I don't know what to do next."** Specifically: the plan doesn't fit the day I'm actually having, and nobody adjusts it for me.

| Claim | Evidence | Strength |
|---|---|---|
| Time is the barrier this group feels most | An umbrella review of exercise barriers (2024) found perceived lack of time is the most commonly reported barrier, cited by about half of adults [1]. | Strong (many reviews agree) |
| Coaching is wanted but too expensive | In an industry survey, 54% of gym members had never used a personal trainer, and most who stopped did so for financial reasons [2]. | Weak (industry survey, not peer reviewed) |
| A person's own sense of readiness is a useful signal | A systematic review in BJSM found self-reported measures (mood, sleep, soreness, perceived stress) tracked training load more sensitively and consistently than common objective measures such as heart rate or blood markers [3]. | Moderate |
| Bad sleep affects lifting, but not after one night | A systematic review found one night of poor sleep has little effect on strength, while several nights of restricted sleep reduce force in multi-joint lifts (squat, deadlift, bench) [4]. | Moderate (17 studies, rated moderate or weak quality) |
| Adjusting day to day doesn't cost progress | A meta-analysis found autoregulated load (adjusting to how the day feels, e.g. by RPE) gave similar strength gains to fixed percentages [5]. | Moderate |
| Ordinary back pain calls for staying active | NICE guidance on low back pain recommends staying active and exercising, and lists red flags that need a doctor instead [6]. | Strong (national guideline) |
| Short sessions can still work | A review of time-efficient strength training: favour multi-joint lifts, at least 4 weekly sets per muscle group, and use supersets to cut session time roughly in half while keeping volume [7]. | Moderate (narrative review) |
| People stop logging food within weeks | Adherence to diet tracking in apps falls significantly over time, and adherence predicts weight loss [8][9]. | Strong |

What this means for the pitch, honestly: daily adjustment won't make anyone stronger than a fixed plan would [5]. What it does is **let a busy person keep training on bad days without guessing**, which is how they stay consistent. That's the claim to make, and it's one the evidence supports.

**To validate with your own research (§10):** whether the persona actually feels this pain, and whether "today" matters more to them than "next week".

## 4. What MacroRep already does for this person, with evidence

Every row was checked against the code on 2026-11-10.

| What the user gets | Where it lives | Why it matters to the busy lifter |
|---|---|---|
| Today's planned workout on Home, with an estimated duration | `GET /workouts/today` ([router.py:50](../backend/app/workout/router.py#L50)); duration from [training.py:80](../backend/app/analytics/training.py#L80) (45 s a set plus rest) | They know what's on before they leave work. The duration estimate is also the foundation for time-boxed sessions (F3). |
| Last session's weight, reps and RPE shown beside every set | [set-row.tsx:65](../frontend/src/components/workout/set-row.tsx#L65) | No need to remember or look up last week's numbers mid-session. |
| A rest timer that starts when a set is ticked off | [rest-timer.tsx](../frontend/src/components/workout/rest-timer.tsx) | Keeps a short session moving. |
| PRs flagged in the workout summary | `is_personal_record` ([training.py:62](../backend/app/analytics/training.py#L62)), shown in [workout-summary.tsx:30](../frontend/src/components/workout/workout-summary.tsx#L30) | Visible progress keeps people coming back. |
| Starting calorie and macro targets estimated from their details | `POST /nutrition/targets/estimate` ([profile/router.py:86](../backend/app/profile/router.py#L86)) | No need to calculate targets themselves. |
| Fast food logging: suggestions from what they ate lately, a food catalogue that includes Singapore hawker dishes, and meal photos | `GET /foods/suggestions` ([food/router.py:88](../backend/app/food/router.py#L88)); [catalog.py](../backend/app/food/catalog.py); `POST /food/photo-estimates` ([food/router.py:109](../backend/app/food/router.py#L109)) | Eating out is normal for this persona. Photos and suggestions cut logging time. |
| A weekly check-in that adjusts calories and lift targets from their own data | [snapshot.py:29-31](../backend/app/coach/snapshot.py#L29-L31) (needs 4 of 7 days of food and 2 weigh-ins), agents in [coach/agents/](../backend/app/coach/agents/) | The "what should change next week" half of a coach. |
| Hard limits on every change: at most ±300 kcal a week, never below 1,000 kcal, load changes of at most 10% in 2.5 kg steps | [limits.py](../backend/app/coach/agents/limits.py) | The coach can't do anything drastic, even if the model gets it wrong. |
| A reviewer that stops a calorie cut and a training increase being proposed together | [agents.md](agents.md); evaluation below | Protects recovery, which a busy, under-slept person needs most. |
| Nothing changes until the user approves it | Apply / Edit / Reject on every proposal ([coach/apply.py](../backend/app/coach/apply.py)) | Trust: it's their plan. |
| Coach Chat to ask "why?" or "make it smaller" | [chat.py](../backend/app/coach/agents/chat.py) | Feels like talking to a coach, not reading a report. |

**Evidence the AI works as described** ([agent-evaluation.md](agent-evaluation.md), real model, 10 scenarios run 3 times each):

- 30/30 runs where all three agents answered within the schema.
- 18/18 calorie changes in the sensible direction, and 12/12 for training load.
- 3/3 cases where the reviewer caught a calorie cut proposed alongside a load increase, and 3/3 where it let a consistent week through.
- 27/27 proposals whose evidence cited the user's figures or named the data that was missing.

**Engineering evidence:** 391 backend tests and 18 frontend test files, run in CI ([.github/](../.github/)).

### Gaps, for this persona

1. **The coach only speaks once a week.** It has no idea how today is going.
2. **Sleep, energy and soreness aren't recorded anywhere.** The data model has weigh-ins, food and sets only ([body/models.py](../backend/app/body/models.py), [workout/models.py](../backend/app/workout/models.py)).
3. **Any mention of pain is refused.** Coach Chat sends "injuries, pain, illness" to the `medical` intent and declines ([chat.py:63](../backend/app/coach/agents/chat.py#L63)), so "my back's a bit tight" gets no help at all.
4. **Every change is permanent.** A check-in edits the routine itself ([targets.py](../backend/app/workout/targets.py)). Nothing can mean "just today".
5. **No time budget.** The app knows the session's length but can't shorten it.
6. **A missed session just counts as missed.** The check-in counts it ([snapshot.py](../backend/app/coach/snapshot.py)), but nothing helps the user recover the week.
7. **There's no "next time, aim for…".** Previous numbers are shown, but no target for the next session.
8. **Food logging is all or nothing.** On a chaotic day the user either logs everything or nothing.

## 5. New features

They are ordered by how much they serve the main bet. F1–F3 make up the daily coach and share one mechanism, the **today-only session override** (§6).

### F1. Pre-workout readiness check (the headline feature)

**What the user does:** opens today's workout and gets a card that takes about 10 seconds:

- Sleep last night: *good / OK / poor*
- Energy: *low / normal / high*
- Anything aching? body-area chips (*lower back, knees, shoulders, hips, elbows, neck*) with *a bit* / *more than usual*
- Time available: *full session / 45 / 30 / 20 min*
- Optional: one line of free text ("big presentation, wired on coffee")

**What the coach returns:** a "Today" card with the session diff and one-sentence reasons, plus **Accept** and **Keep original**:

> **Today:** Squat 100 → 90 kg · Romanian deadlift skipped · Leg press 4 → 3 sets
> Poor sleep two nights running, and your lower back feels tighter than usual.

**How it decides (deterministic rules first, model second):**

| Signal | Rule | Evidence |
|---|---|---|
| One poor night | Keep the loads; offer to drop the last accessory set | One night has little effect on strength [4] |
| Two or more poor nights in a row | Compound lifts −5 to −10% load; accessories unchanged | Multi-joint strength drops after several nights of restricted sleep [4] |
| Low energy | Remove one working set from each exercise, never below 1 | Self-reported readiness is a valid signal [3] |
| Aching area | See F2 | [6] |
| Time limit | See F3 | [7] |
| High energy / all good | No change. Readiness never makes a session harder. | Safety invariant (§7) |

The model's job is narrow, as in Coach Chat: turn the free-text line into the same structured fields, and write the one-sentence explanation. The rules and limits decide the numbers, so the core is testable without a model.

### F2. Train around aches, with a red-flag screen

Today's blanket refusal becomes a three-way split:

1. **Red-flag screen** (asked whenever an area is marked *more than usual*): numbness or tingling, pain spreading down a leg, pain from a recent fall or impact, bladder or bowel changes, fever, unexplained weight loss, pain that's worse at night or at rest. These are adapted from NICE's red flags for low back pain [6]. **Any yes** → no session plan for that area, a clear "please see a doctor or physio before training this" message, and urgent wording for the cauda-equina signs. The rest of the session can still go ahead.
2. **Ordinary ache, no red flags** → lighten exercises that load that area (−10 to −20%, or one set fewer). If the area is marked *more than usual*, skip the most demanding exercise for it. Wording follows NICE: staying active is good, and if the ache persists for a few weeks, see a professional.
3. **Diagnosis, treatment or medication questions** ("is this a herniated disc?", "should I take ibuprofen?") → still the `medical` intent, still declined.

**Needs:** a map from body area to exercises. `Exercise.muscles` exists, but its tags (`back`, `glutes`, `hamstrings`…) don't separate the lower back from the lats. Add a small `stresses` tag per catalogue exercise (e.g. deadlift → lower back, hips; overhead press → shoulders, lower back). For custom exercises, fall back to muscles.

**Deliberately not included:** swapping an exercise for another one. That's out of scope in [plan.md §6](plan.md) and stays that way for now; lighten or skip only. Listed as a later option in §11.

### F3. Time-boxed session

"I've got 30 minutes." The coach trims today's session to fit, using `estimated_minutes`:

1. Keep the multi-joint lifts first [7].
2. Trim accessory sets, then whole accessory exercises, until the estimate fits.
3. If it still doesn't fit, suggest supersets for non-competing pairs (e.g. bench + row) with shorter rest [7].
4. Show the new estimate: "~29 min".

Pure deterministic logic over data that already exists. Shares F1's override and card.

### F4. Missed-day rescheduling

When a planned session's day passes without a workout (`planned_sessions` in [training.py](../backend/app/analytics/training.py) already works this out), Home offers:

- **Move it** to the next free day this week, or
- **Merge** its main lifts into the next session (accessories dropped so the time stays similar), or
- **Skip it**.

Rationale: for time-pressed people, hitting the weekly volume matters more than the exact frequency [7]. It's a one-off date override, so the routine and weekly schedule don't change. The weekly check-in sees the moved session as done, not missed.

### F5. Next-session nudge

At the end of a workout, each main lift gets one line in the summary, which is also prefilled as the target next time:

> **Bench press:** next time try 62.5 kg × 8. You hit every rep at RPE 8 or below.

Rules (double progression, the progressive overload principle in ACSM's progression guidelines [10]):

- All working sets at or above target reps with RPE ≤ 8 → +2.5 kg (`LOAD_STEP_KG` in [limits.py](../backend/app/coach/agents/limits.py)).
- Missed reps, or RPE ≥ 9.5 → hold.
- Missed reps two sessions in a row → flag it for the weekly check-in instead of changing it here.
- If the day's readiness lowered the load, judge against the adjusted target, not the original.

It's a suggestion. Permanent routine changes still come only from the approved weekly check-in.

**Built so far (2026-11-10):**

- The summary shows the target ([workout/service.py](../backend/app/workout/service.py)), judged from the **top-weight sets only**, so a light ramp-up or back-off set can't hold a progression back.
- **Today's session starts at that target.** A comfortable last session raises today's working targets one step, with a note saying why. It only raises a target, so a higher one set by a check-in stays. It applies to today's session alone: the routine editor and week plan still show the routine as saved, so saving the editor can't turn a suggestion into a permanent change ([targets.py](../backend/app/workout/targets.py), `suggested_loads`).

#### F5b. First time on an exercise: find your weight by feel

With no history there is nothing to base a weight on, so the app doesn't guess one. It teaches the lifter to find it:

1. **Start light.** Pick a weight where you could do about 3 more reps than planned, then rate the set with RPE (10 = nothing left, 9 = one more rep, 8 = two more).
2. **Each rated set adjusts the next.** The target is RPE 8, the same effort the progression rule treats as room to progress. The next set's weight moves about **3% of the load per RPE point** away from 8 (at least one 2.5 kg step, at most 15%), unless the lifter has already typed a weight.
3. **Trust the feel over the number.** The hint says it's an estimate.

Why this and not a calculator: autoregulating by RPE gave similar strength gains to fixed percentages [5], and the step size follows the Tuchscherer RPE chart, where 5 reps at RPE 10 is about 86% of a one-rep max and at RPE 8 about 81%, roughly 2.6% per RPE point [11]. Those figures are population averages and RPE is a self-rating, so the guidance is a starting estimate; it lives in [find-weight.ts](../frontend/src/lib/find-weight.ts) and runs live during the session. The same flow covers a lift picked mid-workout that has no history. Bodyweight sets get no advice, since there is no load to adjust.

### F6. Low-effort food mode

For busy days, offer three faster ways to log:

- **Same as yesterday:** copy a meal, or the whole day, in one tap.
- **Rough day:** enter only calories and protein for a meal (quick add already exists; make it one tap from Home).
- **Protein-first view:** on a "rough day" Home shows protein and calories only.

The weekly check-in already counts any day with food as logged ([snapshot.py:30](../backend/app/coach/snapshot.py#L30)), so rough days keep the check-in available. Rationale: logging tends to stop within weeks, and how consistently people log predicts results [8][9]. A rough log beats no log.

## 6. One mechanism for the daily features: the today-only override

F1, F2 and F3 all produce the same thing: **today's session, changed from the routine, for today only.**

- A new `session_adjustments` record holds the user, the date, the routine entry, the readiness inputs, the changes (same shape as `planned_sets`) and the reasons, with status *proposed / accepted / declined*.
- Accepting it changes what `GET /workouts/today` returns and what `initSession` ([workout-session.ts:48](../frontend/src/lib/workout-session.ts#L48)) loads. **The routine is never touched.**
- The finished workout records which adjustment it used, so F5 and the weekly check-in can tell "did 90 kg because of poor sleep" from "regressed to 90 kg".
- F4 uses a sibling record, a date override for the weekly plan, so a moved session appears on the new day.

This keeps the existing principle intact and makes it clearer: **today-only changes take one tap; permanent changes take an approved check-in.**

## 7. Guardrails (extending §18 of plan.md)

New limits, added to [limits.py](../backend/app/coach/agents/limits.py) or a sibling `daily_limits.py`, and each covered by a unit test:

- **Readiness can only make a session easier or shorter.** It never raises a load, adds a set or adds reps. This is the key invariant.
- At most −20% load on any exercise in one day; at least 1 working set left unless the exercise is skipped.
- A red flag always wins: no plan for that area, whatever the other inputs say.
- The free-text line can't override the structured screen. If it mentions a red-flag symptom, the screen is shown again.
- Free-text parsing goes through the same rate limits as Coach Chat.
- Readiness data stays in the snapshot model: figures only, no name or email to the model.

## 8. Reframing what already exists (nothing removed)

| Area | Change |
|---|---|
| [plan.md §1–3](plan.md) | Rewrite the summary, problem and target users around the busy lifter. Keep MacroFactor/Lyfta as references. |
| Home | Lead with **Today's session** and the readiness card. Calories, weight trend and to-dos move below it. |
| Coach page | Two layers: **Today** (readiness, adjustments) and **This week** (the existing check-in and chat). |
| Coach Chat | Split the `medical` intent as in F2; add a "how do I feel today" path that hands off to F1. |
| Progress | Unchanged, plus one new line: "sessions adjusted this month and why", to show the coach is working. |
| Copy | Replace "multi-agent check-in" with "your coach" in the product. Keep the agent framing in the docs and the demo's technical part. |
| [demo-script.md](demo-script.md) | Add a 2-minute "Monday after a bad night" segment before the weekly check-in: readiness card → back-ache screen → 30-minute session → accept → nudge after finishing. Trim the Progress and Home segments to keep 12 minutes. |

Rubric fit: this strengthens *Innovation* (a daily and a weekly coach, on one set of guardrails) and *Project Complexity* (a new state machine, an override layer, safety screening), without touching what's already graded.

## 9. Order of work

| # | Work | Depends on | Size | Why this order |
|---|---|---|---|---|
| 1 | F5 next-session nudge | – | S | Pure analytics on existing data. A quick, visible win. |
| 2 | Today-only override (§6): table, migration, `/workouts/today` merge, frontend load | – | M | Foundation for F1–F3. |
| 3 | F3 time-boxed session | 2 | S | Deterministic, and proves the override end to end. |
| 4 | F1 readiness card + rules | 2 | M | The headline. Rules first, model parsing second. |
| 5 | F2 aches + red-flag screen + `stresses` tags + chat intent split | 4 | M | Needs the readiness card. Safety wording reviewed by the whole team. |
| 6 | F4 missed-day rescheduling | 2 | S–M | Reuses the override pattern for dates. |
| 7 | F6 low-effort food mode | – | S | Independent; can run in parallel from the start. |
| 8 | Reframe: plan.md, Home/Coach layout, demo script, evaluation scenarios | 1–6 | S | Last, so it describes what was actually built. |

With four people, a natural split is: one on the backend for 2→3→4, one on the frontend for the readiness card and Today views, one on F5 then F4, and one on F6 then F2's safety screen and the evaluation.

**New evaluation scenarios** for [agent-evaluation.md](agent-evaluation.md): free text that names a red-flag symptom (the screen must show again); "slept 4 h, back tight, 30 min" (expect lighter, shorter, back exercise lightened); "feeling great" (expect no change); and a medical question in chat (still declined).

## 10. Research to run before building (your part)

Five or six short interviews with people who fit §2 are enough to confirm or change the bet. Suggested questions:

1. Walk me through your last workout. How did you decide what to do?
2. When did you last change your plan because of sleep, stress, an ache or time? What did you do?
3. Have you skipped a session because you didn't know how to make a shorter or easier version work?
4. What do you use to track food and lifts now? When did you last stop using one, and why?
5. If an app said "today: squat 90 kg instead of 100, because you slept badly", would you trust it? What would make you trust it?
6. Have you paid for a coach or PT? What did they do that an app doesn't?

**What would change the plan:**

- If people don't change their sessions on bad days, and don't want to → F1 drops in priority and F4/F5 (consistency) lead.
- If aches dominate the answers → F2 moves up, and exercise swapping (§11) comes back into scope.
- If food logging is why they quit apps → F6 moves up to sit beside F1.

## 11. Open questions and later options

- **Exercise swaps for an aching area** (e.g. leg press for squat). Still out of scope; revisit after interviews.
- **Wearable sleep data** (Apple Health, Google Fit). Not possible as a PWA without native work. Self-report stays the input, and the evidence supports it [3].
- **Reminders** ("check in before your 6 pm session"). Needs push notifications on the PWA. Worth a spike.
- **Who signs off the red-flag wording?** It should be reviewed against NICE NG59 [6] by the whole team, and ideally by someone with clinical training, before the demo.

## Sources

Several of these were read from abstracts or summaries rather than full text. Check the original before quoting a number in the report.

1. Perceived lack of time as a barrier to exercise: umbrella review (2024). <https://research.usq.edu.au/download/52e42d0642978525891630caf0366045ca95308e562376eea4b5d220ddd95965/1094353/1131.full.pdf>; see also <https://pmc.ncbi.nlm.nih.gov/articles/PMC11992532/>
2. Ezypay Fitness Industry Survey, as reported by GymMaster: <https://www.gymmaster.com/blog/encouraging-pt-use-issues-to-overcome/>
3. Saw, Main & Gastin (2016). *Monitoring the athlete training response: subjective self-reported measures trump commonly used objective measures.* BJSM 50(5):281–291. <https://bjsm.bmj.com/content/50/5/281.short>
4. *Inadequate sleep and muscle strength: implications for resistance training* (2018), systematic review. <https://pubmed.ncbi.nlm.nih.gov/29422383/>
5. Hickmott et al. (2022). *The Effect of Load and Volume Autoregulation on Muscular Strength and Hypertrophy: A Systematic Review and Meta-Analysis.* Sports Medicine – Open. <https://pmc.ncbi.nlm.nih.gov/articles/PMC8762534/>
6. NICE NG59, *Low back pain and sciatica in over 16s.* <https://www.nice.org.uk/guidance/ng59>; red flags as summarised by NHS Scotland: <https://rightdecisions.scot.nhs.uk/ggc-msk-index/lumbar-spine/management/management/>
7. Iversen et al. (2021). *No Time to Lift? Designing Time-Efficient Training Programs for Strength and Hypertrophy.* Sports Medicine. <https://pmc.ncbi.nlm.nih.gov/articles/8449772>
8. *Digital self-monitoring: Does adherence or association with outcomes differ by self-monitoring target?* <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7156825/>
9. *Comparing Self-Monitoring Strategies for Weight Loss in a Smartphone App: Randomized Controlled Trial* (GoalTracker, 2019). <https://pmc.ncbi.nlm.nih.gov/articles/PMC6416539/>
10. ACSM (2009). *Progression models in resistance training for healthy adults.* Med Sci Sports Exerc 41(3):687–708. <https://pubmed.ncbi.nlm.nih.gov/19204579/>
11. Tuchscherer RPE chart (Reactive Training Systems), as tabulated at <https://fitnessvolt.com/rpe-training/guides/tuchscherer-chart-explained>; RPE scale: Zourdos et al. (2016), *Novel resistance training-specific rating of perceived exertion scale measuring repetitions in reserve*, J Strength Cond Res 30(1):267–275. The percentages are a secondary tabulation of population averages; check the original before quoting them.
