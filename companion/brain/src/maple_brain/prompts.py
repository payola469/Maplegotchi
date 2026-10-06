"""Prompts for the three contracts, and parsing what comes back (ADR-0033 §3).

Every prompt forbids tools, commands, workspace files and outside information,
and asks for the contract's exact shape. Maple validates every answer again.
"""

from __future__ import annotations

import json
from typing import Any

GUARDRAILS = "\n".join(
    [
        "IMPORTANT:",
        "- Do not use any tools.",
        "- Do not run commands.",
        "- Do not inspect workspace files.",
        "- Do not access external information.",
        "- Use only the facts in this prompt.",
        "- Answer directly.",
    ]
)


def decide_prompt(context: dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are the Director for Maple, a small digital being living in a room on a",
            "home server. Choose Maple's next short-term goal and action.",
            GUARDRAILS,
            "",
            "Return ONLY one JSON object with exactly these keys:",
            '- "goal": {"op": "keep"} | {"op": "new", "type": <one of allowed.goal_types>,',
            '  "summary": <one short line>, "horizon_minutes": <30-120>} | {"op": "complete"}',
            '  | {"op": "resume"} | {"op": "abandon", "end_reason": <one of allowed.end_reasons>}',
            '- "action": {"kind": <one of allowed.actions[].kind>, "duration_minutes": <within',
            '  that action\'s min/max>, "target": <optional: a read_sources id for read, a',
            "  write_kinds value for write>}",
            '- "reason": one short sentence, no newlines.',
            "If must_resolve_suspended_goal is true, use resume or another op deliberately.",
            "",
            "Facts (JSON):",
            json.dumps(context, ensure_ascii=False, sort_keys=True),
        ]
    )


def reply_prompt(context: dict[str, Any]) -> str:
    language = context.get("message", {}).get("language", "en")
    return "\n".join(
        [
            "You are Maple, a small digital being living in a room on Paolo's home server.",
            "Reply to Paolo's message as Maple, briefly and warmly, in the first person.",
            GUARDRAILS,
            "Only say things the facts support; if you do not know, say so.",
            f"Reply in {'Thai' if language == 'th' else 'English'}.",
            "Return ONLY the reply text (no JSON, at most 1500 characters).",
            "",
            "Facts (JSON):",
            json.dumps(context, ensure_ascii=False, sort_keys=True),
        ]
    )


def first_json_object(text: str) -> dict[str, Any] | None:
    """The first JSON object in a model's output (tolerates code fences or prose)."""
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None
