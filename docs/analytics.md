# Analytics formulas

Every number MacroRep derives from a user's logs is computed by plain,
deterministic Python in `backend/app/analytics/`, never by the AI. Each
function takes numbers and dates in and returns numbers out, with no database
access, and is unit-tested against hand-checked values in
`backend/tests/test_analytics_*.py`.

This document records which formula each calculation uses and why, resolving
open decision 6 in `plan.md` §30. All results are **estimates**; see the
limitations at the end.

## Body weight — `analytics/weight.py`

### Trend weight

An exponential moving average over weigh-ins, the approach used by
TrendWeight and Happy Scale:

```
trend₁ = scale₁
trendₙ = trendₙ₋₁ + 0.1 × (scaleₙ − trendₙ₋₁)
```

Daily scale weight swings by 1–2 kg with water and food volume, which would
make raw readings useless for judging a 0.5 kg/week goal. The smoothing factor
0.1 means each reading moves the trend 10% of the way toward itself.

Smoothing is applied **per weigh-in, not per calendar day**: a week without a
weigh-in does not move the trend.

### Rate of change

```
rate (kg/week) = trend change over the period ÷ (days in period ÷ 7)
```

## Nutrition — `analytics/nutrition.py`

### Portion scaling

An entry logged from a saved food stores the food and the quantity; the server
derives its nutrition, so it can be re-scaled when the quantity is edited:

```
servings = quantity                          (entered in servings)
servings = grams ÷ grams per serving         (entered in grams)
nutrient = per-serving value × servings
```

Calories round to whole kcal and macros to 0.1 g, **halves rounding up**. The
browser shows a live preview with `Math.round`, which also rounds halves up;
Python's `round()` rounds halves to even and would disagree (82.5 kcal → 82
instead of 83). Grams need a known serving weight; a food without one can only
be logged in servings.

### Average daily intake

The mean calories over days **with food logged**. Unlogged days are excluded,
not counted as zero: an unlogged day means "unknown", not "ate nothing"
(`plan.md` §8.3). Returns no value when no day is logged.

### Logging completeness

Every day in a period gets one status (`plan.md` §8.3):

| Status | Rule |
|---|---|
| missing | nothing logged |
| partial | logged, but under 50% of the calorie target |
| complete | logged, at least 50% of the calorie target (over target included) |
| in progress | today, whatever was logged |

Today is never judged: at 9 a.m. a logged breakfast would otherwise make every
day read as partial. Counts, adherence, and the target gap below cover
**finished days only**.

"Partial" is only a label. A partial day's intake still counts everywhere
(averages, expenditure, the target gap), because some days really are eaten
well under target; the label flags that the day *may* be under-logged, not
that it is. With no calorie target (0), no logged day is partial.

### Logging adherence

```
adherence (%) = finished days with food logged ÷ finished days × 100, clamped to 0–100
```

Shown as **Days logged**. It measures logging consistency, not whether intake
was on target.

### Target adherence

```
on target (%) = logged days within ±10% of the calorie target ÷ logged days × 100
```

Unlogged days are left out (unknown, not off target). No value when nothing
is logged or there is no target. Shown as **On target**.

### Gap to target

```
target gap (kcal) = Σ (intake − calorie target) over finished logged days
```

Negative means under target. Unlogged days add nothing. Partial days count at
their logged intake, so a week with light days shows as a real shortfall. The
Home card shows it for the last 7 days, the check-in for its 7-day window, and
the Progress page as an average per logged day.

**Limitation:** every day is judged against the **current** calorie target,
not the target in effect that day, because targets aren't versioned yet.
Changing the target re-labels past days.

### Estimated energy expenditure

From energy balance: whatever was eaten and not stored or lost as body mass
was expended.

```
expenditure (kcal/day) = average intake − (trend change (kg) × 7700) ÷ days
```

7700 kcal per kg is the common rule of thumb (≈ 3500 kcal/lb). Losing 0.5 kg
in a week while eating 2000 kcal/day gives an estimate of 2550 kcal/day.

## Training — `analytics/training.py`

Only **working sets** count toward volume, estimated 1RM, and personal
records. Warmups are excluded so a heavy warmup can neither inflate volume nor
mask a genuine PR. The live volume counter shown during a workout follows the
same rule.

### Estimated one-rep max (Epley)

```
e1RM = weight × (1 + reps ÷ 30)
```

With two adjustments:

- **1 rep:** the weight itself. A single is by definition a one-rep max;
  plain Epley would overstate it by 3%.
- **0 reps, or no load:** no estimate. A failed attempt says nothing about
  strength. Counting it as `weight × 1` would let a failed heavy attempt
  register as a personal record.

Epley was chosen over Brzycki because Brzycki breaks down at high reps (it
reaches zero at 37 reps). Both lose accuracy beyond about 10 reps.

### Personal record

A session's best working-set e1RM for an exercise is a PR when it is strictly
greater than the best e1RM from every earlier session, or when there is no
earlier session. Equalling a previous best is not a PR.

### Volume (tonnage)

```
volume (kg) = Σ weight × reps over working sets
```

Weekly volume groups sets by the Monday of the session's ISO week.

The Progress page's week-over-week change compares the **last two completed
weeks** (`percent_change(week before, last week)`), never the current week,
which is still in progress and would otherwise read as a drop every Monday.
It has no value when the earlier week had no volume.

The dashed line on the weekly volume chart is the **average** of the weeks
shown. The API also has a `targetTonnes` field, currently always null,
reserved for a real weekly volume goal (e.g. derived from the workout plan);
the chart switches to it automatically once it is populated.

### Average RPE

The mean RPE of working sets that have an RPE logged, to one decimal. Sets
without an RPE are left out: logging RPE is optional, and a missing value is
not a low effort. No value when no set has an RPE.

- **Per week** (grouped by the session's ISO week): shown in each weekly
  volume bar's tooltip on the Progress page.
- **Avg RPE stat:** the **current week so far**, compared with last week
  **in RPE points** (8.0 → 8.5 is +0.5), not a percentage. Unlike volume,
  which is a total and so reads low for a half-finished week, RPE is an
  average: two sets at RPE 8 on a Wednesday already mean the week averages 8.
  No value until a set with an RPE is logged this week, and no change unless
  last week had RPE too.
- **Check-in:** the mean over the check-in's 7-day window.

### Workout completion

```
planned        = plan days that fell due in the period (see below)
completion (%) = workouts done ÷ planned × 100
```

- **Done** counts every logged session in the period, planned or not, so
  an extra session can make up for a skipped one.
- **Planned** counts each day in the period whose weekday has a planned
  workout, up to yesterday. **Today** counts only once a workout has been
  logged today, so a planned day isn't a miss before there's been a chance
  to train.
- Not capped at 100%: training more often than planned is reported as such.
  No value when nothing was planned.

## Limitations

- **Expenditure is only as good as the logging.** Under-logged meals make
  intake look low and expenditure look low with it. The check-in refuses to
  run below a minimum of logged days for this reason.
- **7700 kcal/kg assumes typical tissue composition.** Early in a diet, water
  and glycogen changes make weight move faster than this predicts.
- **e1RM is an estimate,** most reliable between 1 and 10 reps.
- **Planned workouts use the current plan.** Plans aren't versioned yet, so
  editing the plan changes the planned count, and completion, for past weeks
  too.
- **Days follow the user's timezone.** "Today", weeks, and which day a
  workout belongs to use the IANA timezone on the profile, which the browser
  keeps in sync (`app/shared/timezones.py`), so a 7 a.m. Monday session in
  Singapore counts as Monday even though it is Sunday in UTC. Food and
  weigh-in dates are the browser's local dates as sent. Until a user's
  browser reports its zone, they are on UTC. Past sessions are re-dated in
  the current zone, so someone who moves timezone may see a late-night
  session shift a day.
