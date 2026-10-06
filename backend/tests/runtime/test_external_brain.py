import pytest

from maplegotchi.core.journal import BrainContext, BrainKind, Trigger, TriggerKind
from maplegotchi.runtime.external_brain import ExternalHttpBrain
from tests.core.support import at_local, make_state


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.raise_called = False

    def raise_for_status(self) -> None:
        self.raise_called = True

    def json(self) -> dict[str, object]:
        return self._payload


def make_context() -> BrainContext:
    now = at_local(14)
    state = make_state(at=now)
    trigger = Trigger(TriggerKind.ACTIVITY, "daily:read", "read")
    return BrainContext(
        now=now,
        local_hour=14.0,
        owner_name="Paolo",
        state=state,
        expression=state.expression_at(now),
        snapshot=None,
        triggers=(trigger,),
    )


def test_external_http_brain_identity() -> None:
    brain = ExternalHttpBrain(base_url="http://127.0.0.1:8471")

    assert brain.kind is BrainKind.EXTERNAL
    assert brain.name == "antigravity"
    assert brain.version == "1"


def test_external_http_brain_posts_prompt_and_parses_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    response = FakeResponse(
        {
            "response": (
                '[{"trigger_index":0,'
                '"text":"I spent some time reading.",'
                '"importance":"low",'
                '"template_id":"external.daily.read"}]'
            )
        }
    )

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return response

    monkeypatch.setattr(
        "maplegotchi.runtime.external_brain.httpx2.post",
        fake_post,
    )

    brain = ExternalHttpBrain(
        base_url="http://127.0.0.1:8471",
        timeout_seconds=12.5,
    )

    drafts = brain.compose_journal(make_context())

    assert response.raise_called is True
    assert captured["url"] == "http://127.0.0.1:8471/generate"
    assert captured["timeout"] == 12.5

    body = captured["json"]
    assert isinstance(body, dict)
    prompt = body["prompt"]
    assert isinstance(prompt, str)
    assert "Owner: Paolo" in prompt
    assert "topic=daily:read" in prompt
    for required in (
        "Do not use any tools.",
        "Do not run commands.",
        "Do not inspect workspace files.",
        "Do not access external information.",
        "Return ONLY a JSON array.",
        "trigger_index",
        "importance: one of low, normal, high",
        "template_id",
    ):
        assert required in prompt

    assert len(drafts) == 1
    assert drafts[0].trigger_index == 0
    assert drafts[0].text == "I spent some time reading."


def test_external_http_brain_ignores_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse({"response": "not-json"})

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        return response

    monkeypatch.setattr(
        "maplegotchi.runtime.external_brain.httpx2.post",
        fake_post,
    )

    brain = ExternalHttpBrain(base_url="http://127.0.0.1:8471")

    assert brain.compose_journal(make_context()) == ()
