"""HTTP-backed External Brain selected by the runtime layer."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence

import httpx2

from maplegotchi.core.journal import BrainContext, BrainKind, Importance, JournalDraft

MAX_RESPONSE_BYTES = 64 * 1024


class JournalResponseError(RuntimeError):
    """The companion response exceeds the journal transport boundary."""


class ExternalHttpBrain:
    kind = BrainKind.EXTERNAL
    name = "antigravity"
    version = "1"

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 30.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._monotonic = monotonic

    def compose_journal(self, context: BrainContext) -> Sequence[JournalDraft]:
        deadline = self._monotonic() + self._timeout_seconds

        def remaining() -> float:
            budget = deadline - self._monotonic()
            if budget <= 0:
                raise JournalResponseError("journal deadline exceeded")
            return budget

        prompt = self._build_prompt(context)
        budget = remaining()
        with httpx2.Client(
            timeout=httpx2.Timeout(budget, connect=min(2.0, budget)),
            follow_redirects=False,
            trust_env=False,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            with client.stream(
                "POST", f"{self._base_url}/generate", json={"prompt": prompt}
            ) as response:
                if 300 <= response.status_code < 400:
                    raise JournalResponseError("journal redirects refused")
                response.raise_for_status()
                # The companion uses plain JSON. Refuse content coding so a
                # decompressor cannot allocate an unbounded expansion first.
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise JournalResponseError("journal content encoding refused")
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=4096):
                    remaining()
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise JournalResponseError("journal response too large")
                    body.extend(chunk)
                remaining()
        payload = json.loads(body)
        remaining()
        if not isinstance(payload, dict):
            return ()
        text = payload.get("response")

        if not isinstance(text, str):
            return ()

        drafts = self._parse_response(text)
        remaining()
        return drafts

    def _build_prompt(self, context: BrainContext) -> str:
        triggers = "\n".join(
            f"- {index}: kind={trigger.kind.value}, topic={trigger.topic}, label={trigger.label}"
            for index, trigger in enumerate(context.triggers)
        )

        return (
            "You are Maple's journal-writing brain.\n"
            "IMPORTANT:\n"
            "- Do not use any tools.\n"
            "- Do not run commands.\n"
            "- Do not inspect workspace files.\n"
            "- Do not access external information.\n"
            "- Use only the facts in this prompt.\n"
            "- Answer directly.\n"
            "\n"
            "Return ONLY a JSON array.\n"
            "One object per trigger that should become a journal entry.\n"
            "Each object contains exactly:\n"
            "- trigger_index: integer matching the trigger index\n"
            "- text: one short first-person journal sentence grounded in the facts\n"
            "- importance: one of low, normal, high\n"
            "- template_id: a stable string identifier\n"
            "\n"
            "Facts:\n"
            f"Owner: {context.owner_name}\n"
            f"Local hour: {context.local_hour}\n"
            f"Activity: {context.state.activity.value}\n"
            f"Expression: {context.expression.value}\n"
            "Triggers:\n"
            f"{triggers}\n"
        )

    def _parse_response(self, response: str) -> tuple[JournalDraft, ...]:
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return ()

        if not isinstance(data, list):
            return ()

        drafts: list[JournalDraft] = []

        for item in data:
            if not isinstance(item, dict):
                continue

            try:
                drafts.append(
                    JournalDraft(
                        trigger_index=item["trigger_index"],
                        text=item["text"],
                        importance=Importance(item["importance"]),
                        template_id=item["template_id"],
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue

        return tuple(drafts)
