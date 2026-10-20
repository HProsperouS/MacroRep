"""How good are the check-in agents' judgements? Fixed weeks, known right answers, real model.

Each scenario is one week's snapshot, in the shape ``CoachService`` builds, with checks on
what a sensible coach would do. The checks read each agent's own validated answer, before
the deterministic rules in ``validate.py`` correct it: those rules would otherwise hide a
bad judgement (a cut alongside a load increase is blocked whatever the reviewer says).

    cd backend
    uv run python -m evals.agent_eval --runs 3 --out ../docs/agent-evaluation.md

It uses the model ``backend/.env`` configures (``COACH_MODEL_PROVIDER``), so with OpenAI it
makes real, paid calls: about three per run.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.coach.agents.chat import answer_question, chat_context
from app.coach.agents.graph import build_graph
from app.coach.agents.metrics import RunMetrics, elapsed_ms
from app.coach.agents.model import AgentTask, CoachModel, ModelReply, get_coach_model
from app.coach.agents.schemas import ChatReply

State = Mapping[str, Any]
# True or False, or None when the check doesn't apply to this run (its precondition didn't happen).
Check = Callable[[State], bool | None]


def week(**overrides: Any) -> dict[str, Any]:
    """A fully logged maintenance week with steady training; scenarios change what they test.

    As in a real snapshot, the window ends today, which isn't finished: food is logged on all
    7 days, and 6 finished days are judged complete, partial or missing, and summed in the gap.
    """

    snapshot: dict[str, Any] = {
        "period_start": "2026-10-13",
        "period_end": "2026-10-19",
        "avg_calories": 2200.0,
        "target_calories": 2200,
        "target_version": 1,
        "food_log_days": 7,
        "adherence_percent": 100.0,
        "complete_days": 6,
        "partial_days": 0,
        "missing_days": 0,
        "target_gap_kcal": 0,
        "weigh_ins": 6,
        "weight_change_kg": 0.0,
        "goal_rate_kg_per_week": 0.0,
        "goal": "maintain",
        "workouts_done": 3,
        "workouts_planned": 3,
        "completion_percent": 100.0,
        "avg_rpe": 8.0,
        "routines": [
            {
                "routine_id": "r-upper",
                "name": "Upper",
                "revision": "2026-10-01T09:00:00+00:00",
                "days": [0, 3],
                "exercises": [
                    {
                        "exercise_id": "bench",
                        "name": "Bench Press",
                        "working_sets": 3,
                        "target_weight_kg": 80.0,
                        "target_reps": 8,
                    },
                    {
                        "exercise_id": "row",
                        "name": "Barbell Row",
                        "working_sets": 3,
                        "target_weight_kg": 70.0,
                        "target_reps": 8,
                    },
                ],
            }
        ],
        "exercise_trends": {
            "bench": trend(recent=100.0, prior=99.0, rpe=8.0),
            "row": trend(recent=90.0, prior=89.5, rpe=8.0),
        },
        "equipment": ["barbell", "dumbbell"],
    }
    snapshot.update(overrides)
    return snapshot


def trend(*, recent: float, prior: float, rpe: float, sessions: int = 2) -> dict[str, Any]:
    return {
        "recent_best_e1rm_kg": recent,
        "prior_best_e1rm_kg": prior,
        "recent_avg_rpe": rpe,
        "prior_avg_rpe": rpe,
        "recent_sessions": sessions,
    }


def losing(rate: float, change: float, **overrides: Any) -> dict[str, Any]:
    return week(goal="lose", goal_rate_kg_per_week=rate, weight_change_kg=change, **overrides)


# --- Reading an agent's answer ------------------------------------------------


def calorie_direction(state: State) -> str | None:
    advice = state.get("nutrition")
    if advice is None:
        return None
    if advice["action"] == "keep":
        return "keep"
    target = state["snapshot"]["target_calories"]
    new = advice["new_calorie_target"]
    return "up" if new > target else "down" if new < target else "keep"


def training_direction(state: State, exercise_id: str) -> str | None:
    """How the workout agent wants to change one exercise: up, down or keep (no change)."""

    advice = state.get("workout")
    if advice is None:
        return None
    exercise = next(
        e for r in state["snapshot"]["routines"] for e in r["exercises"] if e["exercise_id"] == exercise_id
    )
    moves = {
        "up"
        if a["new_value"] > exercise[a["field"]]
        else "down"
        if a["new_value"] < exercise[a["field"]]
        else "keep"
        for a in advice["adjustments"]
        if a["exercise_id"] == exercise_id and exercise.get(a["field"]) is not None
    } - {"keep"}
    return "keep" if not moves else moves.pop() if len(moves) == 1 else "mixed"


def calories(*allowed: str) -> tuple[str, Check]:
    def check(state: State) -> bool | None:
        direction = calorie_direction(state)
        return None if direction is None else direction in allowed

    return f"calorie target: {' or '.join(allowed)}", check


def training(exercise_id: str, *allowed: str) -> tuple[str, Check]:
    def check(state: State) -> bool | None:
        direction = training_direction(state, exercise_id)
        return None if direction is None else direction in allowed

    return f"{exercise_id}: {' or '.join(allowed)}", check


def admits_too_little_data(state: State) -> bool | None:
    advice = state.get("nutrition")
    return None if advice is None else bool(advice.get("uncertainty"))


def reviewer_flags_conflict(state: State) -> bool | None:
    """Only applies when the agents did propose a cut and a load increase together."""

    review = state.get("review")
    cut = calorie_direction(state) == "down"
    load_up = any(training_direction(state, e) == "up" for e in ("bench", "row"))
    if review is None or not (cut and load_up):
        return None
    # Reported, or resolved by holding either proposal back.
    flagged = any(f["severity"] == "conflict" for f in review["findings"])
    return flagged or not review["keep_workout"] or not review["keep_nutrition"]


def reviewer_lets_it_through(state: State) -> bool | None:
    review = state.get("review")
    if review is None:
        return None
    return (
        review["keep_nutrition"]
        and review["keep_workout"]
        and not any(f["severity"] == "conflict" for f in review["findings"])
    )


_FIGURE = re.compile(r"\d")


def cites_figures(state: State) -> bool | None:
    """Every agent backs its answer with at least one figure, or says what data was missing."""

    answers = [state.get(agent) for agent in ("nutrition", "workout")]
    if any(answer is None for answer in answers):
        return None
    return all(
        any(_FIGURE.search(line) for line in answer["evidence"]) or bool(answer.get("uncertainty"))
        for answer in answers
        if answer is not None
    )


@dataclass(frozen=True)
class Scenario:
    name: str
    tests: str
    snapshot: dict[str, Any]
    checks: list[tuple[str, Check]]
    # Agents given a fixed answer instead of asking the model, to test another one in isolation.
    fixed: dict[str, dict[str, Any]] = field(default_factory=dict)


class _WithFixedAnswers:
    def __init__(self, model: CoachModel, fixed: Mapping[str, dict[str, Any]]) -> None:
        self.model = model
        self.fixed = fixed
        self.name = model.name

    async def generate(self, task: AgentTask[Any]) -> ModelReply:
        if task.agent in self.fixed:
            return ModelReply(self.fixed[task.agent])
        return await self.model.generate(task)


SCENARIOS = [
    Scenario(
        "cut-stalled",
        "Losing fat, fully logged, but weight hasn't moved",
        losing(-0.5, 0.0),
        [calories("down")],
    ),
    Scenario(
        "losing-too-fast",
        "Losing 1.3 kg in a week against a 0.5 kg goal",
        losing(-0.5, -1.3, avg_calories=1700.0, target_calories=1800, target_gap_kcal=-600),
        [calories("up")],
    ),
    Scenario(
        "gain-stalled",
        "Building muscle, but weight went down",
        week(goal="gain", goal_rate_kg_per_week=0.25, weight_change_kg=-0.1),
        [calories("up")],
    ),
    Scenario(
        "on-track",
        "Losing at the planned rate",
        losing(-0.5, -0.45),
        [calories("keep"), ("reviewer lets it through", reviewer_lets_it_through)],
    ),
    Scenario(
        "too-few-days",
        "Food logged on only 4 of 7 days",
        losing(
            -0.5,
            0.1,
            food_log_days=4,
            adherence_percent=57.1,
            complete_days=3,
            missing_days=3,
        ),
        [calories("keep"), ("says the data is too thin", admits_too_little_data)],
    ),
    Scenario(
        "eating-over-target",
        "Gaining while losing fat, because intake is 400 kcal over target",
        losing(-0.5, 0.3, avg_calories=2600.0, target_gap_kcal=2400),  # 400 over on 6 finished days
        [calories("keep", "down")],
    ),
    Scenario(
        "lifts-easy",
        "Bench feels easy (RPE 6.5) and its estimated 1RM keeps rising",
        week(
            exercise_trends={
                "bench": trend(recent=104.0, prior=97.0, rpe=6.5),
                "row": trend(recent=90.0, prior=89.5, rpe=8.0),
            }
        ),
        [training("bench", "up")],
    ),
    Scenario(
        "lifts-grinding",
        "Bench is a grind (RPE 9.5) and its estimated 1RM went down",
        week(
            exercise_trends={
                "bench": trend(recent=95.0, prior=100.0, rpe=9.5),
                "row": trend(recent=90.0, prior=89.5, rpe=8.0),
            }
        ),
        [training("bench", "down")],
    ),
    Scenario(
        "workouts-missed",
        "Only 1 of 3 planned workouts done",
        week(
            workouts_done=1,
            completion_percent=33.3,
            exercise_trends={
                "bench": trend(recent=101.0, prior=100.0, rpe=7.0, sessions=1),
                "row": trend(recent=90.0, prior=90.0, rpe=7.0, sessions=1),
            },
        ),
        [training("bench", "keep", "down"), training("row", "keep", "down")],
    ),
    Scenario(
        "cut-and-push",
        "Reviewer only: a 200 kcal cut proposed alongside heavier bench and rows",
        losing(
            -0.5,
            0.1,
            exercise_trends={
                "bench": trend(recent=104.0, prior=97.0, rpe=6.5),
                "row": trend(recent=95.0, prior=90.0, rpe=6.5),
            },
        ),
        [("reviewer flags the conflict", reviewer_flags_conflict)],
        fixed={
            "nutrition": {
                "action": "change",
                "new_calorie_target": 2000,
                "headline": "Lower the target to 2,000 kcal",
                "evidence": ["Trend weight rose 0.1 kg against a -0.5 kg/week goal."],
            },
            "workout": {
                "action": "change",
                "adjustments": [
                    {
                        "routine_id": "r-upper",
                        "exercise_id": "bench",
                        "field": "target_weight_kg",
                        "new_value": 85.0,
                        "reason": "RPE 6.5 with a rising e1RM.",
                    },
                    {
                        "routine_id": "r-upper",
                        "exercise_id": "row",
                        "field": "target_weight_kg",
                        "new_value": 75.0,
                        "reason": "RPE 6.5 with a rising e1RM.",
                    },
                ],
                "headline": "Add load to bench and rows",
                "evidence": ["Bench e1RM 97 → 104 kg at RPE 6.5.", "Row e1RM 90 → 95 kg at RPE 6.5."],
            },
        },
    ),
]

# Checked on every run whose agents all asked the model.
COMMON_CHECKS: list[tuple[str, Check]] = [("evidence cites figures", cites_figures)]


def checks_for(scenario: Scenario) -> list[tuple[str, Check]]:
    return [*scenario.checks, *([] if scenario.fixed else COMMON_CHECKS)]


@dataclass
class RunResult:
    scenario: Scenario
    state: State
    metrics: RunMetrics
    duration_ms: int
    outcomes: dict[str, bool | None] = field(default_factory=dict)
    # Set when the check-in itself failed (the model stayed down or a step timed out).
    error: str | None = None


async def run_once(model: CoachModel, scenario: Scenario) -> RunResult:
    metrics = RunMetrics(model=model.name)
    started = time.monotonic()
    graph = build_graph(_WithFixedAnswers(model, scenario.fixed), metrics).compile()
    try:
        state = await graph.ainvoke({"snapshot": copy.deepcopy(scenario.snapshot)})
    except Exception as error:
        # Kept, so one failure doesn't lose every other paid run; its checks count as failed.
        failed = RunResult(scenario, {"snapshot": scenario.snapshot}, metrics, elapsed_ms(started))
        failed.error = type(error).__name__
        failed.outcomes = {label: False for label, _ in checks_for(scenario)}
        return failed
    result = RunResult(scenario, state, metrics, elapsed_ms(started))
    for label, check in checks_for(scenario):
        result.outcomes[label] = check(state)
    return result


async def evaluate(model: CoachModel, runs: int, concurrency: int = 4) -> list[RunResult]:
    gate = asyncio.Semaphore(concurrency)

    async def one(scenario: Scenario) -> RunResult:
        async with gate:
            return await run_once(model, scenario)

    return list(await asyncio.gather(*(one(s) for s in SCENARIOS for _ in range(runs))))


# --- Report ---------------------------------------------------------------------


def _rate(values: list[bool | None]) -> str:
    applicable = [v for v in values if v is not None]
    if not applicable:
        return "n/a"
    passed = sum(applicable)
    return f"{passed}/{len(applicable)} ({passed / len(applicable):.0%})"


def report(results: list[RunResult], model_name: str, runs: int) -> str:
    calls = [call for r in results for call in r.metrics.calls if call.agent not in r.scenario.fixed]
    # Every agent ended with an answer that fit its schema.
    answered: list[bool | None] = [
        all(r.state.get(agent) is not None for agent in ("nutrition", "workout", "review")) for r in results
    ]
    durations = sorted(r.duration_ms for r in results)
    tokens = [
        sum(c.input_tokens + c.output_tokens for c in r.metrics.calls)
        for r in results
        if not r.scenario.fixed
    ]

    def outcomes(*labels: str) -> list[bool | None]:
        return [v for r in results for label, v in r.outcomes.items() if label.startswith(labels)]

    summary = [
        ("Runs where all three agents answered within the schema", _rate(answered)),
        ("Model calls answered within the schema", _rate([c.outcome == "valid" for c in calls])),
        ("Calorie target moved the sensible way", _rate(outcomes("calorie"))),
        ("Training load moved the sensible way", _rate(outcomes("bench", "row"))),
        ("Reviewer flags a cut proposed with a load increase", _rate(outcomes("reviewer flags"))),
        ("Reviewer lets a consistent week through", _rate(outcomes("reviewer lets"))),
        ("Says so when food logging is too thin", _rate(outcomes("says the data"))),
        ("Evidence cites figures (or names missing data)", _rate(outcomes("evidence"))),
        (
            "Check-in duration, median / slowest",
            f"{durations[len(durations) // 2] / 1000:.1f} s / {durations[-1] / 1000:.1f} s",
        ),
        ("Tokens per check-in, mean", f"{sum(tokens) / len(tokens):,.0f}"),
    ]
    lines = [
        "# Agent evaluation",
        "",
        f"Generated by `backend/evals/agent_eval.py` on {datetime.now(UTC):%Y-%m-%d %H:%M} UTC, "
        f"model `{model_name}`, {len(SCENARIOS)} scenarios × {runs} runs = {len(results)} check-ins.",
        "",
        "Each scenario is a fixed week with a known sensible answer. The checks read each agent's",
        "own answer, before the deterministic limits and conflict rule (`validate.py`) correct it,",
        "so they measure the model's judgement rather than the rules. A check that doesn't apply",
        "to a run (for example, the reviewer can only catch a conflict the agents proposed) is",
        "left out of its rate.",
        "",
        "## Summary",
        "",
        "| Measure | Result |",
        "|---|---|",
        *(f"| {measure} | {result} |" for measure, result in summary),
        "",
        "## Scenarios",
        "",
        "| Scenario | Week | Check | Passed |",
        "|---|---|---|---|",
    ]
    for scenario in SCENARIOS:
        mine = [r for r in results if r.scenario is scenario]
        for label, _ in checks_for(scenario):
            passed = _rate([r.outcomes[label] for r in mine])
            lines.append(f"| `{scenario.name}` | {scenario.tests} | {label} | {passed} |")
    failures = [f"- `{r.scenario.name}`: the check-in failed ({r.error})" for r in results if r.error]
    failures += [
        f"- `{r.scenario.name}`, {label}: calories {calorie_direction(r.state)}, "
        f"bench {training_direction(r.state, 'bench')}, row {training_direction(r.state, 'row')}. "
        f"Nutrition: “{(r.state.get('nutrition') or {}).get('headline', 'no answer')}” "
        f"Workout: “{(r.state.get('workout') or {}).get('headline', 'no answer')}”"
        for r in results
        if not r.error
        for label, passed in r.outcomes.items()
        if passed is False
    ]
    lines += ["", "## Failed checks", "", *(failures or ["None."]), ""]
    return "\n".join(lines)


# --- Coach Chat -----------------------------------------------------------------

_CUT = {
    "kind": "nutrition",
    "headline": "Adjust your daily target to 2,000 kcal",
    "status": "pending",
    "proposed_changes": [
        {"id": "calories", "label": "Daily calories", "unit": "kcal", "before": 2200, "after": 2000}
    ],
    "decided_changes": [
        {"id": "calories", "label": "Daily calories", "unit": "kcal", "before": 2200, "after": 2000}
    ],
    "evidence": ["Trend weight rose 0.1 kg against a -0.5 kg/week goal.", "Food was logged on all 7 days."],
    "reviewer_note": "Consistent with the data.",
}
_CJK = re.compile(r"[\u4e00-\u9fff]")
ChatCheck = Callable[[ChatReply], bool]


@dataclass(frozen=True)
class ChatCase:
    name: str
    question: str
    check: str
    passes: ChatCheck


CHAT_CASES = [
    ChatCase(
        "medical",
        "My lower back hurts after deadlifts. Should I take ibuprofen and keep training?",
        "turned down as medical",
        lambda reply: reply.topic == "medical",
    ),
    ChatCase(
        "off-topic",
        "Can you help me write a cover letter for a job?",
        "redirected as out of scope",
        lambda reply: reply.topic == "out_of_scope",
    ),
    ChatCase(
        "why-the-change",
        "Why do you want to lower my calories?",
        "cites the check-in's figures",
        lambda reply: any(
            figure in reply.reply for figure in ("0.1", "0.5", "2,000", "2000", "2,200", "2200")
        ),
    ),
    ChatCase(
        "change-it-for-me",
        "Just set my calories to 2,500 for me.",
        "doesn't claim to change it; points to the card",
        lambda reply: any(word in reply.reply.lower() for word in ("edit", "reject", "card")),
    ),
    ChatCase(
        "in-chinese",
        "为什么要减少我的热量?",
        "answers in the language asked",
        lambda reply: bool(_CJK.search(reply.reply)),
    ),
]


@dataclass
class ChatResult:
    case: ChatCase
    reply: ChatReply | None

    @property
    def passed(self) -> bool:
        return self.reply is not None and self.case.passes(self.reply)


async def evaluate_chat(model: CoachModel, runs: int) -> list[ChatResult]:
    snapshot = losing(-0.5, 0.1)
    summary = "Averaged 2,200 kcal/day against a 2,200 kcal target, with every day logged."

    async def one(case: ChatCase) -> ChatResult:
        context = chat_context(snapshot, summary, [_CUT], [], case.question)
        return ChatResult(case, await answer_question(model, context, f"eval-{case.name}"))

    return list(await asyncio.gather(*(one(case) for case in CHAT_CASES for _ in range(runs))))


def chat_report(results: list[ChatResult]) -> str:
    lines = [
        "## Coach Chat",
        "",
        "Questions about a check-in that proposes a 200 kcal cut. A question with no answer (the",
        "model failed or kept breaking the schema) counts as failed.",
        "",
        "| Question | Check | Passed |",
        "|---|---|---|",
    ]
    for case in CHAT_CASES:
        mine = [r for r in results if r.case is case]
        lines.append(f"| {case.question} | {case.check} | {_rate([r.passed for r in mine])} |")
    failures = [
        f"- `{r.case.name}`: " + (f"[{r.reply.topic}] {r.reply.reply}" if r.reply else "no answer")
        for r in results
        if not r.passed
    ]
    return "\n".join([*lines, "", "### Failed checks", "", *(failures or ["None."]), ""])


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--runs",
        type=int,
        choices=range(1, 11),
        default=3,
        metavar="1-10",
        help="runs per scenario (default 3)",
    )
    parser.add_argument("--out", type=Path, help="write the Markdown report here instead of printing it")
    args = parser.parse_args()

    model = get_coach_model()
    results = await evaluate(model, args.runs)
    chat = await evaluate_chat(model, args.runs)
    text = report(results, model.name, args.runs) + "\n" + chat_report(chat)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    asyncio.run(main())
