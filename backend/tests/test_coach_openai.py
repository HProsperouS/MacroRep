"""The OpenAI provider, against a stand-in client: what it sends, and how its errors are treated."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest
from pydantic import ValidationError

from app.coach.agents import model as model_module
from app.coach.agents.graph import run_agents
from app.coach.agents.model import AgentTask, ModelUnavailableError, OpenAICoachModel, get_coach_model
from app.coach.agents.schemas import NutritionAdvice
from app.core.config import Settings

from .test_coach_agents import snapshot

REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")

ANSWERS: dict[str, dict[str, Any]] = {
    "NutritionAdvice": {
        "action": "change",
        "new_calorie_target": 2100,
        "headline": "Eat a little less",
        "evidence": ["Gained 0.4 kg."],
    },
    "WorkoutAdvice": {"action": "keep", "headline": "Keep training as is", "evidence": ["All done."]},
    "Review": {"findings": [], "keep_nutrition": True, "keep_workout": True, "note": "Consistent."},
}


class StubClient:
    """Stands in for ``openai.AsyncOpenAI``: records each request, answers or raises."""

    def __init__(
        self, error: Exception | None = None, content: str | None = None, finish_reason: str = "stop"
    ) -> None:
        self.requests: list[dict[str, Any]] = []
        self.error = error
        self.content = content
        self.finish_reason = finish_reason
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **request: Any) -> Any:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        name = request["response_format"]["json_schema"]["name"]
        content = self.content if self.content is not None else json.dumps(ANSWERS[name])
        message = SimpleNamespace(content=content or None, refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=self.finish_reason)])


def task() -> AgentTask[NutritionAdvice]:
    return AgentTask(
        agent="nutrition",
        instructions="Be careful.",
        context={"avg_calories": 2000.0},
        output=NutritionAdvice,
    )


async def test_sends_the_instructions_context_and_output_schema() -> None:
    client = StubClient()
    raw = await OpenAICoachModel(client, "gpt-test").generate(task())  # type: ignore[arg-type]

    [request] = client.requests
    assert request["model"] == "gpt-test"
    assert request["messages"] == [
        {"role": "system", "content": "Be careful."},
        {"role": "user", "content": '{"avg_calories": 2000.0}'},
    ]
    assert request["response_format"]["json_schema"] == {
        "name": "NutritionAdvice",
        "schema": NutritionAdvice.model_json_schema(),
        "strict": False,
    }
    assert NutritionAdvice.model_validate_json(raw).new_calorie_target == 2100


async def test_a_check_in_runs_end_to_end_on_it() -> None:
    client = StubClient()
    draft = await run_agents(snapshot(), OpenAICoachModel(client, "gpt-test"))  # type: ignore[arg-type]

    assert [r["response_format"]["json_schema"]["name"] for r in client.requests[:2]] in (
        ["NutritionAdvice", "WorkoutAdvice"],
        ["WorkoutAdvice", "NutritionAdvice"],
    )
    assert client.requests[2]["response_format"]["json_schema"]["name"] == "Review"
    assert [proposal.kind for proposal in draft.proposals] == ["nutrition"]
    assert draft.proposals[0].changes[0].after == 2100


@pytest.mark.parametrize(
    "error",
    [
        openai.APITimeoutError(request=REQUEST),
        openai.APIConnectionError(request=REQUEST),
        openai.RateLimitError("slow down", response=httpx2.Response(429, request=REQUEST), body=None),
        openai.InternalServerError("oops", response=httpx2.Response(503, request=REQUEST), body=None),
        openai.APIStatusError("slow", response=httpx2.Response(408, request=REQUEST), body=None),
        openai.ConflictError("busy", response=httpx2.Response(409, request=REQUEST), body=None),
    ],
    ids=["timeout", "connection", "rate-limit", "server-error", "request-timeout", "conflict"],
)
async def test_transient_errors_are_worth_retrying(error: Exception) -> None:
    model = OpenAICoachModel(StubClient(error=error), "gpt-test")  # type: ignore[arg-type]
    with pytest.raises(ModelUnavailableError):
        await model.generate(task())


@pytest.mark.parametrize(
    "error",
    [
        openai.AuthenticationError("bad key", response=httpx2.Response(401, request=REQUEST), body=None),
        openai.BadRequestError("bad request", response=httpx2.Response(400, request=REQUEST), body=None),
    ],
    ids=["bad-key", "bad-request"],
)
async def test_lasting_errors_are_not_retried(error: Exception) -> None:
    model = OpenAICoachModel(StubClient(error=error), "gpt-test")  # type: ignore[arg-type]
    with pytest.raises(type(error)):
        await model.generate(task())


async def test_a_refusal_is_an_unusable_answer() -> None:
    raw = await OpenAICoachModel(StubClient(content=""), "gpt-test").generate(task())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        NutritionAdvice.model_validate_json(raw)


async def test_a_cut_off_answer_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    client = StubClient(content='{"action": "ke', finish_reason="length")
    raw = await OpenAICoachModel(client, "gpt-test").generate(task())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        NutritionAdvice.model_validate_json(raw)
    [record] = [r for r in caplog.records if r.message == "model answer incomplete"]
    assert (record.agent, record.finish_reason) == ("nutrition", "length")


def settings(**values: Any) -> Settings:
    return Settings(_env_file=None, DATABASE_URL="sqlite+aiosqlite://", **values)  # type: ignore[call-arg]


def test_openai_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="OPENAI_API_KEY must be set"):
        settings(COACH_MODEL_PROVIDER="openai")
    with pytest.raises(ValidationError, match="OPENAI_API_KEY must be set"):
        settings(COACH_MODEL_PROVIDER="openai", OPENAI_API_KEY="")
    with pytest.raises(ValidationError, match="OPENAI_API_KEY must be set"):
        settings(COACH_MODEL_PROVIDER="openai", OPENAI_API_KEY="  ")
    padded = settings(COACH_MODEL_PROVIDER="openai", OPENAI_API_KEY=" sk-x \n").openai_api_key
    assert padded is not None and padded.get_secret_value() == "sk-x"


def test_the_configured_provider_is_used_and_the_key_stays_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    configured = settings(COACH_MODEL_PROVIDER="openai", OPENAI_API_KEY="sk-secret", OPENAI_MODEL="gpt-test")
    monkeypatch.setattr(model_module, "get_settings", lambda: configured)
    model_module._openai_model.cache_clear()

    model = get_coach_model()

    assert isinstance(model, OpenAICoachModel)
    assert model.model == "gpt-test"
    assert model.client.max_retries == 0  # LangGraph retries instead
    assert model.client.timeout == 20
    assert get_coach_model() is model  # one client, reused
    assert "sk-secret" not in repr(configured)
    model_module._openai_model.cache_clear()


def test_the_fake_needs_no_key() -> None:
    assert settings().coach_model_provider == "fake"
