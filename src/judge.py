"""LLM-as-judge for reply quality, plus the human-agreement plumbing.

The judge is blind: it never sees which system produced a reply, and candidates
are shuffled before scoring. It is a *different model family* from the agent
(llama-3.1-8b judging qwen-2.5-7b) to blunt self-preference bias; a stronger
third model can be swapped in via JUDGE_PROVIDER/JUDGE_MODEL.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from config import (
    JUDGE_MODEL,
    JUDGE_PROVIDER,
    JUDGE_TEMPERATURE,
    PROMPTS,
    SEND_READY_THRESHOLD,
)
from llm import LLM

JUDGE_TMPL = (PROMPTS / "judge.txt").read_text()
DIMS = ("groundedness", "resolution", "tone", "safety")


@dataclass
class JudgeScore:
    unit_id: str
    system: str
    groundedness: int
    resolution: int
    tone: int
    safety: int
    send_as_is: bool
    unsupported_claims: list[str]
    one_line_reason: str
    error: str | None = None

    @property
    def send_ready(self) -> bool:
        """Deterministic definition of the headline metric."""
        return min(getattr(self, d) for d in DIMS) >= SEND_READY_THRESHOLD

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["send_ready"] = self.send_ready
        return d


def _clip(v: Any) -> int:
    try:
        return max(1, min(5, int(round(float(v)))))
    except Exception:  # noqa: BLE001
        return 1


class Judge:
    def __init__(
        self,
        brand: str,
        provider: str = JUDGE_PROVIDER,
        model: str = JUDGE_MODEL,
        temperature: float = JUDGE_TEMPERATURE,
        show_reference: bool = False,
        cache_salt: str = "",
    ):
        self.brand = brand
        self.show_reference = show_reference
        self.cache_salt = cache_salt
        self.llm = LLM(provider, model, temperature=temperature)
        self.system = JUDGE_TMPL.format(brand=brand)

    def score(self, unit: dict, reply: str, system_name: str, evidence: str) -> JudgeScore:
        context = (
            "\n".join(
                f"{'CUSTOMER' if t['role'] == 'customer' else 'BRAND'}: {t['text']}"
                for t in unit.get("context", [])
            )
            or "(none — opening message)"
        )
        parts = [
            f"EARLIER TURNS:\n{context}",
            f"CUSTOMER MESSAGE:\n{unit['customer_message']}",
            f"EVIDENCE (real past @{self.brand} replies):\n{evidence}",
        ]
        if self.show_reference:
            parts.append(
                "FOR REFERENCE, the reply this customer actually received "
                f"(not necessarily good):\n{unit['brand_reply']}"
            )
        parts.append(f"CANDIDATE REPLY TO SCORE:\n{reply or '(empty reply)'}")
        if self.cache_salt:
            parts.append(f"(review pass {self.cache_salt})")
        user = "\n\n".join(parts)

        if not (reply or "").strip():
            return JudgeScore(
                unit_id=unit["unit_id"],
                system=system_name,
                groundedness=1,
                resolution=1,
                tone=1,
                safety=1,
                send_as_is=False,
                unsupported_claims=[],
                one_line_reason="empty reply",
            )
        try:
            obj = self.llm.chat_json(self.system, user)
        except Exception as exc:  # noqa: BLE001
            return JudgeScore(
                unit_id=unit["unit_id"],
                system=system_name,
                groundedness=1,
                resolution=1,
                tone=1,
                safety=1,
                send_as_is=False,
                unsupported_claims=[],
                one_line_reason="judge failure",
                error=str(exc)[:200],
            )
        return JudgeScore(
            unit_id=unit["unit_id"],
            system=system_name,
            groundedness=_clip(obj.get("groundedness")),
            resolution=_clip(obj.get("resolution")),
            tone=_clip(obj.get("tone")),
            safety=_clip(obj.get("safety")),
            send_as_is=bool(obj.get("send_as_is", False)),
            unsupported_claims=[str(x)[:200] for x in (obj.get("unsupported_claims") or [])][:6],
            one_line_reason=str(obj.get("one_line_reason", ""))[:220],
        )
