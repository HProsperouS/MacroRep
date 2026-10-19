"""Reading and adjusting a routine exercise's working-set targets."""

from __future__ import annotations

from app.workout.targets import adjust_targets, working_targets

WARMUP = {"kind": "warmup", "target_weight_kg": 40.0, "target_reps": 10}
WORK = {"kind": "working", "target_weight_kg": 100.0, "target_reps": 5}
LIGHT = {"kind": "working", "target_weight_kg": 90.0, "target_reps": 8}
DROP = {"kind": "drop", "target_weight_kg": 70.0, "target_reps": 12}


def test_targets_describe_the_working_sets_only() -> None:
    assert working_targets([WARMUP, WORK, LIGHT, DROP]) == {
        "working_sets": 2.0,
        "target_weight_kg": 100.0,
        "target_reps": 8.0,
    }
    assert working_targets([WARMUP]) == {"working_sets": 0.0, "target_weight_kg": None, "target_reps": None}


def test_more_working_sets_copy_the_last_one_in_place() -> None:
    sets = adjust_targets([WARMUP, WORK, LIGHT, DROP], "working_sets", 4)
    assert sets == [WARMUP, WORK, LIGHT, LIGHT, LIGHT, DROP]


def test_fewer_working_sets_drop_the_last_ones() -> None:
    assert adjust_targets([WARMUP, WORK, LIGHT, DROP], "working_sets", 1) == [WARMUP, WORK, DROP]


def test_a_new_target_keeps_the_sets_shape_and_leaves_other_sets_alone() -> None:
    # The heaviest set gets 95; the 90 kg set keeps its proportion (85.5, rounded towards 90: 87.5).
    sets = adjust_targets([WARMUP, WORK, LIGHT, DROP], "target_weight_kg", 95.0)
    assert [s["target_weight_kg"] for s in sets] == [40.0, 95.0, 87.5, 70.0]
    # The highest reps (8) become 6, so every working set loses 2.
    sets = adjust_targets([WARMUP, WORK, LIGHT, DROP], "target_reps", 6)
    assert [s["target_reps"] for s in sets] == [10, 3, 6, 12]


def test_a_pyramid_stays_a_pyramid_and_no_set_moves_more_than_the_whole() -> None:
    pyramid = [
        {"kind": "working", "target_weight_kg": w, "target_reps": r}
        for w, r in ((80.0, 12), (90.0, 10), (100.0, 8))
    ]
    lighter = adjust_targets(pyramid, "target_weight_kg", 95.0)
    assert [s["target_weight_kg"] for s in lighter] == [77.5, 87.5, 95.0]
    # The highest reps (12) become 14: every set gains 2.
    more_reps = adjust_targets(pyramid, "target_reps", 14)
    assert [s["target_reps"] for s in more_reps] == [14, 12, 10]


def test_sets_and_reps_are_whole_numbers() -> None:
    assert working_targets([WORK, LIGHT]) == {"working_sets": 2, "target_weight_kg": 100.0, "target_reps": 8}
    assert all(isinstance(v, int) for k, v in working_targets([WORK]).items() if k != "target_weight_kg")


def test_adjusting_leaves_the_original_untouched() -> None:
    original = [WARMUP, WORK]
    adjust_targets(original, "target_weight_kg", 50.0)
    assert original == [WARMUP, WORK]
    assert WORK["target_weight_kg"] == 100.0


def test_a_first_working_set_can_be_added() -> None:
    assert adjust_targets([WARMUP], "working_sets", 1) == [
        WARMUP,
        {"kind": "working", "target_weight_kg": None, "target_reps": None},
    ]


def test_rounding_to_plates_never_moves_a_light_set_past_the_whole_change() -> None:
    sets = [{"kind": "working", "target_weight_kg": w, "target_reps": 5} for w in (20.0, 100.0)]
    # -10% overall: 20 kg scaled is 18, which no plate step reaches within 10%, so it stays at 20.
    assert [s["target_weight_kg"] for s in adjust_targets(sets, "target_weight_kg", 90.0)] == [20.0, 90.0]
    assert [s["target_weight_kg"] for s in adjust_targets(sets, "target_weight_kg", 110.0)] == [20.0, 110.0]
