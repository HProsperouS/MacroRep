"""Estimating the foods in a meal photo with the model. Nothing is logged and the photo isn't kept."""

from __future__ import annotations

from app.coach.agents.model import CoachModel
from app.coach.agents.schemas import PhotoEstimate
from app.coach.agents.vision import estimate_photo
from app.shared.exceptions import Unavailable
from app.shared.rate_limit import PHOTOS_PER_USER, counted_attempt, user_limiter


class PhotoService:
    def __init__(self, model: CoachModel, *, rate_limits: bool) -> None:
        """With ``rate_limits``, each user gets ``PHOTOS_PER_USER`` photos (then 429)."""

        self.model = model
        self.rate_limits = rate_limits

    async def estimate(self, image: str, user_id: str) -> PhotoEstimate:
        """Estimate the foods in a meal photo, for the user to correct before logging any of them."""

        with counted_attempt(
            ("photo", user_id),
            PHOTOS_PER_USER,
            reason="That's a lot of photos for now.",
            counts=user_limiter,
            enabled=self.rate_limits,
        ):
            estimate = await estimate_photo(self.model, image, user_id)
            if estimate is None:
                raise Unavailable("The photo couldn't be read just now. Please try again.")
        return estimate
