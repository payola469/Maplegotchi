"""Journal HTTP controls, using only in-memory transports."""

from collections.abc import Callable, Iterator

import httpx2
import pytest

from maplegotchi.core.journal import BrainContext, BrainKind, Trigger, TriggerKind
from maplegotchi.runtime.external_brain import (
    MAX_RESPONSE_BYTES,
    ExternalHttpBrain,
    JournalResponseError,
)
from tests.core.support import at_local, make_state


def make_context() -> BrainContext:
    now = at_local(14)
    state = make_state(at=now)
    return BrainContext(
        now=now,
        local_hour=14,
        owner_name="owner",
        state=state,
        expression=state.expression_at(now),
        snapshot=None,
        triggers=(Trigger(TriggerKind.ACTIVITY, "daily:read", "read"),),
    )


def transport(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx2.Request], httpx2.Response]
) -> list[dict[str, object]]:
    original = httpx2.Client
    captured: list[dict[str, object]] = []

    def client(**kwargs: object) -> httpx2.Client:
        captured.append(kwargs)
        return original(transport=httpx2.MockTransport(handler), **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("maplegotchi.runtime.external_brain.httpx2.Client", client)
    return captured


def test_external_http_brain_posts_prompt_and_parses_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST" and request.url.path == "/generate"
        for phrase in (b"Do not use any tools", b"Do not run commands", b"trigger_index"):
            assert phrase in request.content
        return httpx2.Response(
            200,
            json={
                "response": '[{"trigger_index":0,"text":"I read quietly.",'
                '"importance":"low","template_id":"external.read"}]'
            },
        )

    captured = transport(monkeypatch, handler)
    brain = ExternalHttpBrain(base_url="http://127.0.0.1:8471")
    drafts = brain.compose_journal(make_context())
    assert (brain.kind, brain.name, brain.version) == (BrainKind.EXTERNAL, "antigravity", "1")
    assert len(drafts) == 1 and drafts[0].text == "I read quietly."
    assert captured[0]["follow_redirects"] is False
    assert captured[0]["trust_env"] is False
    timeout = captured[0]["timeout"]
    assert (
        isinstance(timeout, httpx2.Timeout) and timeout.connect is not None and timeout.connect <= 2
    )


@pytest.mark.parametrize("extra", [0, 1])
def test_decoded_response_limit(monkeypatch: pytest.MonkeyPatch, extra: int) -> None:
    body = b'{"response":"[]"}'
    body += b" " * (MAX_RESPONSE_BYTES + extra - len(body))
    transport(monkeypatch, lambda request: httpx2.Response(200, content=body))
    brain = ExternalHttpBrain(base_url="http://127.0.0.1:8471")
    if extra:
        with pytest.raises(JournalResponseError, match="too large"):
            brain.compose_journal(make_context())
    else:
        assert brain.compose_journal(make_context()) == ()


class Trickle(httpx2.SyncByteStream):
    def __init__(self, clock: list[float]) -> None:
        self.clock = clock
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        for _ in range(4):
            self.clock[0] += 10
            yield b" " * 4096

    def close(self) -> None:
        self.closed = True


def test_trickle_stream_hits_absolute_deadline_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]
    stream = Trickle(clock)
    transport(monkeypatch, lambda request: httpx2.Response(200, stream=stream))
    brain = ExternalHttpBrain(base_url="http://127.0.0.1:8471", monotonic=lambda: clock[0])
    with pytest.raises(JournalResponseError, match="deadline"):
        brain.compose_journal(make_context())
    assert stream.closed and clock[0] == 30


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirect_is_refused(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    requests = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(status, headers={"Location": "http://127.0.0.1:9999/"})

    transport(monkeypatch, handler)
    with pytest.raises(JournalResponseError, match="redirects"):
        ExternalHttpBrain(base_url="http://127.0.0.1:8471").compose_journal(make_context())
    assert len(requests) == 1


@pytest.mark.parametrize(
    "payload",
    [[], {"response": 3}, {"response": "not-json"}, {"response": '[{"trigger_index":0}]'}],
)
def test_unusable_response_has_no_drafts(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    transport(monkeypatch, lambda request: httpx2.Response(200, json=payload))
    assert ExternalHttpBrain(base_url="http://127.0.0.1:8471").compose_journal(make_context()) == ()


def test_malformed_envelope_raises_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx2.Response(200, content=b"not-json")
    transport(monkeypatch, lambda request: response)
    with pytest.raises(ValueError):
        ExternalHttpBrain(base_url="http://127.0.0.1:8471").compose_journal(make_context())
    assert response.is_closed


def test_network_timeout_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        raise httpx2.ReadTimeout("test timeout")

    transport(monkeypatch, handler)
    with pytest.raises(httpx2.ReadTimeout):
        ExternalHttpBrain(base_url="http://127.0.0.1:8471").compose_journal(make_context())
    assert len(calls) == 1


def test_compressed_response_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    transport(
        monkeypatch,
        lambda request: httpx2.Response(200, headers={"Content-Encoding": "br"}, content=b""),
    )
    with pytest.raises(JournalResponseError, match="encoding"):
        ExternalHttpBrain(base_url="http://127.0.0.1:8471").compose_journal(make_context())


@pytest.mark.parametrize("phase", ["prompt", "parse"])
def test_deadline_includes_request_preparation_and_parsing(
    monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    now = [0.0]
    captured = transport(monkeypatch, lambda request: httpx2.Response(200, json={"response": "[]"}))
    brain = ExternalHttpBrain(base_url="http://127.0.0.1:8471", monotonic=lambda: now[0])
    if phase == "prompt":

        def prompt(context: BrainContext) -> str:
            now[0] = 31
            return "test"

        monkeypatch.setattr(brain, "_build_prompt", prompt)
    else:

        def parse(text: str) -> tuple[()]:
            now[0] = 31
            return ()

        monkeypatch.setattr(brain, "_parse_response", parse)
    with pytest.raises(JournalResponseError, match="deadline"):
        brain.compose_journal(make_context())
    assert len(captured) == (0 if phase == "prompt" else 1)
