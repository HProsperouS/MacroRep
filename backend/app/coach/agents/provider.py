"""Which ``CoachModel`` the app uses, by ``COACH_MODEL_PROVIDER``."""

from __future__ import annotations

from app.core.config import get_settings

from .fake_model import FakeCoachModel
from .model import CoachModel
from .openai_model import cached_openai_model


def get_coach_model() -> CoachModel:
    settings = get_settings()
    if settings.coach_model_provider == "fake":
        return FakeCoachModel()
    key = settings.openai_api_key
    assert key is not None  # Settings refuses "openai" without a key
    return cached_openai_model(
        key.get_secret_value(),
        settings.openai_model,
        settings.openai_timeout_seconds,
        settings.openai_reasoning_effort,
    )
