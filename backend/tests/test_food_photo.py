"""Meal-photo estimates: what's accepted, what the model sees, and what comes back."""

from __future__ import annotations

import base64
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.coach.agents.fake_model import FAKE_PHOTO_ESTIMATE
from app.coach.agents.model import AgentTask, ModelReply, ModelUnavailableError
from app.coach.agents.openai_model import _user_content
from app.coach.agents.schemas import PhotoEstimate
from app.food.photo import MAX_PHOTO_BYTES
from app.shared.rate_limit import PHOTOS_PER_USER
from tests.fakes import ScriptedModel, use_model
from tests.helpers import register_user

PHOTOS = "/api/v1/food/photo-estimates"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 200


def data_url(kind: str, data: bytes) -> str:
    return f"data:image/{kind};base64,{base64.b64encode(data).decode()}"


@pytest.mark.parametrize(("kind", "data"), [("jpeg", JPEG), ("png", PNG), ("webp", WEBP)])
def test_a_photo_gets_an_estimate_to_check(client: TestClient, kind: str, data: bytes) -> None:
    headers = register_user(client)

    response = client.post(PHOTOS, headers=headers, json={"image": data_url(kind, data)})

    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body["items"]] == [item["name"] for item in FAKE_PHOTO_ESTIMATE["items"]]
    assert body["items"][0] == {
        "name": "Chicken rice",
        "portion": "1 plate",
        "grams": 350,
        "calories": 600,
        "protein": 30,
        "carbs": 75,
        "fat": 18,
    }
    assert body["note"]
    entries = client.get(
        "/api/v1/food-log", headers=headers, params={"date": date.today().isoformat()}
    ).json()
    assert entries["entries"] == [], "nothing is logged until the user confirms"


@pytest.mark.parametrize(
    ("image", "reason"),
    [
        (data_url("jpeg", PNG), "isn't the image type it says it is"),
        ("data:image/gif;base64,R0lGODlh", "JPEG, PNG or WebP"),
        ("data:text/plain;base64,aGVsbG8=", "JPEG, PNG or WebP"),
        ("data:image/jpeg;base64,not base64!", "JPEG, PNG or WebP"),
        (data_url("jpeg", b"\xff\xd8\xff" + b"\x00" * MAX_PHOTO_BYTES), "larger than 4 MB"),
    ],
    ids=["mislabelled", "gif", "not-an-image", "not-base64", "too-big"],
)
def test_only_reasonable_images_are_accepted(client: TestClient, image: str, reason: str) -> None:
    headers = register_user(client)
    response = client.post(PHOTOS, headers=headers, json={"image": image})

    assert response.status_code == 422
    assert reason in response.text
    assert "base64," not in response.text, "the image isn't echoed back"


def test_the_model_sees_the_photo_and_nothing_about_the_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedModel(food_photo={"items": [], "note": "No food here."})
    use_model(monkeypatch, model)
    headers = register_user(client)
    image = data_url("jpeg", JPEG)

    response = client.post(PHOTOS, headers=headers, json={"image": image})

    assert response.json() == {"items": [], "note": "No food here."}
    [task] = model.tasks
    assert (task.agent, task.images, task.context) == ("food_photo", (image,), {})


def test_calories_far_below_the_macros_are_raised_to_match(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = {
        "name": "Steak",
        "portion": "1 steak",
        "grams": 250,
        "calories": 60,
        "protein": 60,
        "carbs": 0,
        "fat": 30,
    }
    use_model(monkeypatch, ScriptedModel(food_photo={"items": [item]}))
    headers = register_user(client)

    [estimated] = client.post(PHOTOS, headers=headers, json={"image": data_url("jpeg", JPEG)}).json()["items"]

    assert estimated["calories"] == 60 * 4 + 30 * 9, "so logging it isn't refused"


def test_an_unreadable_photo_says_try_again(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedModel(food_photo=ModelUnavailableError("down"))
    use_model(monkeypatch, model)
    headers = register_user(client)

    response = client.post(PHOTOS, headers=headers, json={"image": data_url("jpeg", JPEG)})

    assert response.status_code == 503
    assert "try again" in response.json()["detail"]
    assert len(model.tasks) == 2, "a transient error is tried once more"


def test_photos_per_user_are_limited(client: TestClient) -> None:
    headers = register_user(client)
    for _ in range(PHOTOS_PER_USER.attempts):
        assert client.post(PHOTOS, headers=headers, json={"image": data_url("jpeg", JPEG)}).status_code == 200

    refused = client.post(PHOTOS, headers=headers, json={"image": data_url("jpeg", JPEG)})

    assert refused.status_code == 429
    assert refused.json()["detail"].startswith("That's a lot of photos for now.")


def test_a_confirmed_item_is_logged_as_from_a_photo(client: TestClient) -> None:
    headers = register_user(client)
    today = date.today().isoformat()

    created = client.post(
        "/api/v1/food-log/entries",
        headers=headers,
        json={
            "date": today,
            "meal": "lunch",
            "name": "Chicken rice",
            "amountLabel": "350 g · photo estimate",
            "source": "photo",
            "calories": 600,
            "protein": 30,
            "carbs": 75,
            "fat": 18,
        },
    )

    assert created.status_code == 201
    [entry] = client.get("/api/v1/food-log", headers=headers, params={"date": today}).json()["entries"]
    assert entry["source"] == "photo"


def test_the_photo_goes_to_openai_after_the_context() -> None:
    task = AgentTask(
        agent="food_photo",
        instructions="x",
        context={},
        output=PhotoEstimate,
        images=("data:image/jpeg;base64,AA==",),
    )
    assert _user_content(task) == [
        {"type": "text", "text": "{}"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AA=="}},
    ]


def test_a_body_over_the_limit_is_refused_before_it_is_read(client: TestClient) -> None:
    from app.shared.request_guard import MAX_BODY_BYTES

    headers = register_user(client)
    response = client.post(
        PHOTOS,
        headers={**headers, "Content-Type": "application/json"},
        content=b'{"image": "' + b"A" * MAX_BODY_BYTES + b'"}',
    )
    assert response.status_code == 413


async def test_a_streamed_body_is_cut_off_once_past_the_limit() -> None:
    from app.shared.request_guard import MAX_BODY_BYTES, LimitBodySizeMiddleware

    reads = 0
    sent: list[dict[str, Any]] = []

    async def app(scope: Any, receive: Any, send: Any) -> None:
        while (await receive()).get("more_body"):
            pass
        raise AssertionError("the whole body was read")

    async def receive() -> dict[str, Any]:
        nonlocal reads
        reads += 1
        return {"type": "http.request", "body": b"x" * (1024 * 1024), "more_body": True}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""}
    await LimitBodySizeMiddleware(app)(scope, receive, send)

    assert sent[0]["status"] == 413
    assert reads == MAX_BODY_BYTES // (1024 * 1024) + 1, "stopped at the first chunk past the limit"


def test_raised_calories_stay_within_the_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    item = {
        "name": "Feast",
        "portion": "a lot",
        "grams": 2000,
        "calories": 100,
        "protein": 300,
        "carbs": 500,
        "fat": 300,
    }
    use_model(monkeypatch, ScriptedModel(food_photo={"items": [item]}))
    headers = register_user(client)

    [estimated] = client.post(PHOTOS, headers=headers, json={"image": data_url("jpeg", JPEG)}).json()["items"]

    assert estimated["calories"] == 5000


def test_a_failed_estimate_doesnt_use_up_a_photo(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.shared.rate_limit import user_limiter

    use_model(monkeypatch, ScriptedModel(food_photo=ModelUnavailableError("down")))
    headers = register_user(client)
    assert client.post(PHOTOS, headers=headers, json={"image": data_url("jpeg", JPEG)}).status_code == 503

    assert all(not hits for key, hits in user_limiter._hits.items() if key[0] == "photo")  # noqa: SLF001


def test_no_retry_once_half_the_time_is_gone(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.coach.agents import vision

    class SlowThenDown:
        name = "slow"
        calls = 0

        async def generate(self, task: AgentTask[Any]) -> ModelReply:
            self.calls += 1
            await asyncio.sleep(0.06)
            raise ModelUnavailableError("timed out")

    monkeypatch.setattr(vision, "PHOTO_TIMEOUT_SECONDS", 0.1)
    model = SlowThenDown()
    use_model(monkeypatch, model)
    headers = register_user(client)

    assert client.post(PHOTOS, headers=headers, json={"image": data_url("jpeg", JPEG)}).status_code == 503
    assert model.calls == 1, "a retry starting at 60 ms of 100 couldn't finish"
