/**
 * Finding a first working weight by feel. With no history to go on, the lifter starts light
 * and rates each set with RPE (10 = nothing left, 9 = one more rep, 8 = two more); the next
 * set moves toward RPE 8, the same effort the server treats as "room to progress".
 *
 * The size of a step follows the common Tuchscherer RPE chart, where 5 reps at RPE 10 is
 * about 86% of a one-rep max and at RPE 8 about 81%: roughly 2.6% of the load per RPE point.
 * Those percentages are population averages, so this is a starting estimate, not a prescription.
 */

export const TARGET_RPE = 8
/** Share of the load to move per RPE point away from the target. */
const SHARE_PER_RPE_POINT = 0.03
/** A single adjustment never moves the load by more than this share. */
const MAX_SHARE = 0.15
const STEP_KG = 2.5
/** An RPE this close to the target is close enough to stay put. */
const CLOSE_ENOUGH = 0.5
/** Reps in reserve to aim for on the very first set: RPE 7, a little under the target. */
export const FIRST_SET_REPS_IN_RESERVE = 3

export type WeightAdvice = {
  weightKg: number
  direction: "up" | "down" | "hold"
  message: string
}

function roundToStep(kg: number) {
  return Math.round(kg / STEP_KG) * STEP_KG
}

function show(kg: number) {
  return `${Number.isInteger(kg) ? kg : kg.toFixed(1)} kg`
}

/** What to lift next, given the weight just used and the RPE it felt like. Null without a load to adjust. */
export function adviseWeight(weightKg: number, rpe: number): WeightAdvice | null {
  if (!(weightKg > 0) || !(rpe >= 1 && rpe <= 10)) return null
  const gap = TARGET_RPE - rpe
  if (Math.abs(gap) <= CLOSE_ENOUGH) {
    return { weightKg, direction: "hold", message: `RPE ${rpe} is about right. Stay at ${show(weightKg)}.` }
  }
  const share = Math.min(Math.abs(gap) * SHARE_PER_RPE_POINT, MAX_SHARE)
  const change = Math.max(STEP_KG, roundToStep(weightKg * share))
  if (gap > 0) {
    const next = weightKg + change
    return { weightKg: next, direction: "up", message: `RPE ${rpe} left plenty in the tank. Try ${show(next)}.` }
  }
  const next = Math.max(STEP_KG, weightKg - change)
  return { weightKg: next, direction: "down", message: `RPE ${rpe} was close to your limit. Try ${show(next)}.` }
}

type FindingSet = { kind: string; weight: string; reps: string; rpe: string; done: boolean }

export type FindWeightStep =
  | { step: "start"; reps: number | null }
  | { step: "rate" }
  | { step: "advice"; advice: WeightAdvice }

/** Where the lifter is in finding their weight, from the exercise's sets as they stand.
 *  Null once a set was done with no weight on the bar: a bodyweight move has no load to adjust. */
export function findWeightStep(sets: FindingSet[]): FindWeightStep | null {
  const working = sets.filter((set) => set.kind === "working")
  const latest = [...working].reverse().find((set) => set.done)
  if (!latest) {
    const reps = Number(working.find((set) => set.reps.trim() !== "")?.reps)
    return { step: "start", reps: Number.isInteger(reps) && reps > 0 ? reps : null }
  }
  if (!(Number(latest.weight) > 0)) return null
  const rpe = latest.rpe.trim() === "" ? Number.NaN : Number(latest.rpe)
  const advice = adviseWeight(Number(latest.weight), rpe)
  return advice ? { step: "advice", advice } : { step: "rate" }
}
