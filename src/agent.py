"""The support agent: triage -> route -> grounded draft.

Architecture (see DECISIONS.md #4): the LLM does *perception* (intent + risk
signals), deterministic code does *policy* (auto vs escalate), and the LLM then
does *generation* constrained to retrieved evidence. A pure-LLM router is kept as
an ablation so the value of the policy layer is measurable, not assumed.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import taxonomy
from config import (
    AGENT_MODEL,
    AGENT_PROVIDER,
    AGENT_TEMPERATURE,
    PROMPTS,
    RETRIEVAL_K,
)
from llm import LLM
from retrieval import HistoryIndex, Neighbour

CLASSIFY_TMPL = (PROMPTS / "classify.txt").read_text()
DRAFT_TMPL = (PROMPTS / "draft.txt").read_text()

HOUSE_STYLE = (
    "Short, warm, first person plural ('we'). Acknowledge the problem in the first "
    "clause. One concrete next step. Moves anything account-specific to DM."
)


@dataclass
class AgentOutput:
    unit_id: str
    intent: str
    confidence: str
    summary: str
    signals: dict[str, bool]
    route: str
    route_reason: str
    reply: str
    commitments: list[str]
    retrieval: list[dict] = field(default_factory=list)
    used_evidence_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _render_context(unit: dict) -> str:
    if not unit.get("context"):
        return "(no earlier turns — this is the opening message of the thread)"
    return "\n".join(
        f"{'CUSTOMER' if t['role'] == 'customer' else 'BRAND'}: {t['text']}"
        for t in unit["context"]
    )


def _render_evidence(neighbours: list[Neighbour]) -> str:
    if not neighbours:
        return "(no similar past message found — treat as unprecedented)"
    out = []
    for n in neighbours:
        out.append(
            f"[{n.unit_id}] (similarity {n.similarity})\n"
            f"  past customer: {n.customer_message}\n"
            f"  brand replied: {n.brand_reply}"
        )
    return "\n".join(out)


class SupportAgent:
    def __init__(
        self,
        index: HistoryIndex | None,
        brand: str,
        provider: str = AGENT_PROVIDER,
        model: str = AGENT_MODEL,
        router: str = "policy",
        use_retrieval: bool = True,
        k: int = RETRIEVAL_K,
    ):
        self.index = index
        self.brand = brand
        self.router = router
        self.use_retrieval = use_retrieval and index is not None
        self.k = k
        self.llm = LLM(provider, model, temperature=AGENT_TEMPERATURE)
        self.signal_keys = [s["key"] for s in taxonomy.risk_signals()]

    # ------------------------------------------------------------- prompts
    def _classify_system(self) -> str:
        signals = "\n".join(
            f"- {s['key']}: {s['definition']}" for s in taxonomy.risk_signals()
        )
        keys = ", ".join(f'"{k}": bool' for k in self.signal_keys)
        return CLASSIFY_TMPL.format(
            brand=self.brand,
            codebook=taxonomy.codebook_block(),
            risk_signals=signals,
            signal_keys=keys,
        )

    # ------------------------------------------------------------- steps
    def triage(self, unit: dict) -> dict:
        user = (
            f"EARLIER TURNS:\n{_render_context(unit)}\n\n"
            f"INCOMING CUSTOMER MESSAGE:\n{unit['customer_message']}"
        )
        obj = self.llm.chat_json(self._classify_system(), user)
        intent = str(obj.get("intent", "")).strip()
        valid = taxonomy.intent_names()
        if intent not in valid:
            lowered = {v.lower(): v for v in valid}
            intent = lowered.get(intent.lower(), "other_unclear")
        signals = obj.get("signals") or {}
        signals = {k: bool(signals.get(k, False)) for k in self.signal_keys}
        conf = str(obj.get("confidence", "medium")).lower()
        if conf not in {"high", "medium", "low"}:
            conf = "medium"
        return {
            "intent": intent,
            "confidence": conf,
            "summary": str(obj.get("summary", ""))[:160],
            "signals": signals,
            "entities": obj.get("entities") or {},
        }

    def decide_route(
        self, triage: dict, neighbours: list[Neighbour]
    ) -> tuple[str, str]:
        """Deterministic escalation policy. Returns (route, reason)."""
        reasons: list[str] = []
        hard = [s["key"] for s in taxonomy.risk_signals() if s.get("hard_escalate")]
        for key in hard:
            if triage["signals"].get(key):
                reasons.append(f"risk signal `{key}`")
        if triage["intent"] in taxonomy.escalate_always():
            reasons.append(f"intent `{triage['intent']}` is never auto-handled")
        if triage["intent"] not in taxonomy.auto_eligible() and not reasons:
            reasons.append(f"intent `{triage['intent']}` is not on the auto-handle list")
        if triage["confidence"] == "low":
            reasons.append("triage confidence is low")
        support = max((n.similarity for n in neighbours), default=0.0)
        if self.use_retrieval and support < 0.18:
            reasons.append(f"weak historical precedent (best similarity {support:.2f})")
        if reasons:
            return "escalate", "; ".join(reasons[:3])
        return (
            "auto",
            f"intent `{triage['intent']}` is auto-eligible, no risk signals, "
            f"precedent similarity {support:.2f}",
        )

    def decide_route_llm(self, unit: dict, triage: dict, neighbours: list[Neighbour]) -> tuple[str, str]:
        system = (
            f"You are the routing layer of the @{self.brand} support inbox. Decide "
            "whether a draft reply can be sent automatically with no human review "
            "('auto'), or must be handed to a human ('escalate'). Escalate anything "
            "involving money, account access or security, legal or regulatory threats, "
            "an explicit request for a human, safety-of-life content, or anything with "
            "no clear precedent. Return ONLY "
            '{"route": "auto"|"escalate", "reason": str} with reason under 20 words.'
        )
        user = (
            f"INTENT: {triage['intent']} (confidence {triage['confidence']})\n"
            f"SIGNALS: {json.dumps(triage['signals'])}\n"
            f"CUSTOMER MESSAGE: {unit['customer_message']}\n"
            f"BEST PRECEDENT SIMILARITY: {max((n.similarity for n in neighbours), default=0.0):.2f}"
        )
        obj = self.llm.chat_json(system, user)
        route = str(obj.get("route", "escalate")).lower()
        if route not in {"auto", "escalate"}:
            route = "escalate"
        return route, str(obj.get("reason", ""))[:200]

    def draft(
        self,
        unit: dict,
        triage: dict,
        route: str,
        route_reason: str,
        neighbours: list[Neighbour],
    ) -> dict:
        system = DRAFT_TMPL.format(
            brand=self.brand,
            style=HOUSE_STYLE,
            evidence=_render_evidence(neighbours),
            intent=triage["intent"],
            route=route,
            route_reason=route_reason,
        )
        user = (
            f"EARLIER TURNS:\n{_render_context(unit)}\n\n"
            f"INCOMING CUSTOMER MESSAGE:\n{unit['customer_message']}"
        )
        obj = self.llm.chat_json(system, user)
        reply = str(obj.get("reply", "")).strip().replace("\n", " ")
        return {
            "reply": reply[:400],
            "used_evidence_ids": [str(x) for x in (obj.get("used_evidence_ids") or [])][:8],
            "commitments": [str(x) for x in (obj.get("commitments") or [])][:8],
        }

    # ------------------------------------------------------------- driver
    def run(self, unit: dict) -> AgentOutput:
        errors: list[str] = []
        neighbours: list[Neighbour] = []
        if self.use_retrieval:
            neighbours = self.index.search(
                unit["customer_message"],
                k=self.k,
                exclude_conversation=unit["conversation_id"],
            )
        try:
            triage = self.triage(unit)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"triage_failed: {exc}")
            triage = {
                "intent": "other_unclear",
                "confidence": "low",
                "summary": "",
                "signals": {k: False for k in self.signal_keys},
                "entities": {},
            }
        if self.router == "llm":
            try:
                route, reason = self.decide_route_llm(unit, triage, neighbours)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"router_failed: {exc}")
                route, reason = "escalate", "router failure -> fail safe"
        else:
            route, reason = self.decide_route(triage, neighbours)
        try:
            drafted = self.draft(unit, triage, route, reason, neighbours)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"draft_failed: {exc}")
            drafted = {"reply": "", "used_evidence_ids": [], "commitments": []}
        return AgentOutput(
            unit_id=unit["unit_id"],
            intent=triage["intent"],
            confidence=triage["confidence"],
            summary=triage["summary"],
            signals=triage["signals"],
            route=route,
            route_reason=reason,
            reply=drafted["reply"],
            commitments=drafted["commitments"],
            used_evidence_ids=drafted["used_evidence_ids"],
            retrieval=[asdict(n) for n in neighbours],
            errors=errors,
        )
