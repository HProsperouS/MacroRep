"""Writing an accepted proposal to the user's targets or routines."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext
from app.profile.models import TargetSource
from app.profile.repository import ProfileRepository
from app.profile.schemas import DailyTargets
from app.profile.service import TARGETS_CHANGED, record_targets
from app.shared.exceptions import Conflict, Invalid

# The same bounds as the targets the user sets, so a proposal can't set one they couldn't type in.
from app.shared.validation import MAX_TARGET_CALORIES, MIN_TARGET_CALORIES, ensure_plausible_calories
from app.workout.models import WorkoutPlanEntry, WorkoutPlanExercise
from app.workout.repository import WorkoutPlanRepository
from app.workout.targets import TARGET_FIELDS, TargetField, adjust_targets, routine_revision, working_targets

from .agents import limits
from .agents.validate import training_change_error
from .models import CheckIn as CheckInModel
from .models import Proposal as ProposalModel

ROUTINE_GONE = (
    "The routine this change was for no longer has that exercise. Reject it and start a new check-in."
)
ROUTINE_CHANGED = (
    "Your routine changed after this check-in was made, so its proposal is out of date. "
    "Reject it and start a new check-in."
)
TARGETS_OUT_OF_DATE = (
    "Your targets changed after this check-in was made, so its proposal is out of date. "
    "Reject it and start a new check-in."
)


class ProposalApplier:
    def __init__(
        self, session: AsyncSession, profiles: ProfileRepository, plans: WorkoutPlanRepository
    ) -> None:
        self.session = session
        self.profiles = profiles
        self.plans = plans

    async def nutrition(
        self,
        actor: ActorContext,
        check_in: CheckInModel,
        proposal: ProposalModel,
        changes: list[dict[str, object]],
    ) -> None:
        """Record an accepted calorie change as a new version of the user's targets, from today.

        Raises 409 when the targets changed after the check-in was made, since the proposal
        was worked out from the old ones, and 422 when the new target is outside the range
        the app allows or far below what the macros add up to. Either way nothing is changed.
        """

        calories = next((change["after"] for change in changes if change["id"] == "calories"), None)
        if calories is None:
            return
        target = round(cast(float, calories))
        profile = await self.profiles.get(actor.actor_id)
        current = await self.profiles.current_targets(actor.actor_id)
        if profile is None or current is None:
            raise Conflict("Set up your profile before applying targets")
        expected_version = (check_in.input_snapshot or {}).get("target_version")
        # Check-ins made before targets were versioned have no version to compare.
        if expected_version is not None and expected_version != current.version:
            raise Conflict(TARGETS_OUT_OF_DATE)
        if not MIN_TARGET_CALORIES <= target <= MAX_TARGET_CALORIES:
            raise Invalid(
                f"A daily target of {target:,} kcal is outside the allowed "
                f"{MIN_TARGET_CALORIES:,}-{MAX_TARGET_CALORIES:,} kcal. Edit it to a value in range.",
            )
        protein, carbs, fat = float(current.protein_g), float(current.carbs_g), float(current.fat_g)
        try:
            ensure_plausible_calories(target, protein, carbs, fat)
        except ValueError as error:
            raise Invalid(str(error)) from error
        try:
            # Numbered after the targets checked above: a change saved since then is refused, not overwritten.
            await record_targets(
                self.profiles,
                profile,
                current,
                DailyTargets(calories=target, protein=protein, carbs=carbs, fat=fat),
                TargetSource.CHECK_IN,
                proposal_id=proposal.id,
            )
        except IntegrityError:
            await self.session.rollback()
            raise Conflict(TARGETS_CHANGED) from None

    async def training(
        self, actor: ActorContext, check_in: CheckInModel, changes: list[dict[str, object]]
    ) -> None:
        """Write accepted training changes to the user's routines, all of them or none.

        Raises 409 when a routine or exercise is gone, or the routine was saved again after
        the check-in (so the proposal is out of date), and 422 when an edited value is past
        the limits. Nothing is changed then. Every change is checked against the routine as
        the check-in saw it, then applied weight and reps first, the number of sets last.
        """

        seen = {
            cast(str, routine["routine_id"]): routine
            for routine in cast(list[dict[str, Any]], (check_in.input_snapshot or {}).get("routines") or [])
        }
        routines: dict[str, WorkoutPlanEntry] = {}
        exercises: dict[str, list[WorkoutPlanExercise]] = {}
        planned_changes: dict[str, tuple[WorkoutPlanExercise, list[tuple[TargetField, float]]]] = {}
        for change in changes:
            routine_id, exercise_id, field = (
                change.get("routine_id"),
                change.get("exercise_id"),
                change.get("field"),
            )
            if (
                not isinstance(routine_id, str)
                or not isinstance(exercise_id, str)
                or field not in TARGET_FIELDS
            ):
                raise Invalid("This change can't be applied to a routine.")
            if routine_id not in routines:
                routine = await self.plans.get(routine_id)
                if routine is None or routine.owner_id != actor.actor_id:
                    raise Conflict(ROUTINE_GONE)
                # Snapshots from before revisions were recorded fall back to the value check below.
                revision = seen.get(routine_id, {}).get("revision")
                if revision is not None and revision != routine_revision(routine):
                    raise Conflict(ROUTINE_CHANGED)
                routines[routine_id] = routine
                exercises[routine_id] = await self.plans.list_exercises(routine_id)
            # The first occurrence, as the snapshot described it to the agent.
            planned = next((pe for pe in exercises[routine_id] if pe.exercise_id == exercise_id), None)
            if planned is None:
                raise Conflict(ROUTINE_GONE)
            target: TargetField = field
            before, after = float(cast(float, change["before"])), float(cast(float, change["after"]))
            current = working_targets(planned.planned_sets)[target]
            if current is None or abs(current - before) > 1e-9:
                raise Conflict(ROUTINE_CHANGED)
            error = training_change_error(target, before, after)
            if error is not None:
                raise Invalid(f"{change['label']}: {error}")
            planned_changes.setdefault(planned.id, (planned, []))[1].append((target, after))

        for planned, targets in planned_changes.values():
            sets = list(planned.planned_sets)
            # Sets last, so a weight change scales the sets the check-in saw, then any are added or dropped.
            for target, after in sorted(targets, key=lambda item: item[0] == "working_sets"):
                sets = adjust_targets(sets, target, after, load_step=limits.LOAD_STEP_KG)
            planned.planned_sets = sets
        for routine in routines.values():
            routine.touch()
