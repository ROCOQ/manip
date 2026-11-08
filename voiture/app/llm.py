"""Appels à l'API Claude : boucle d'un agent spécialisé (recherche web + rapport structuré)."""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from . import config
from .agents import AgentSpec

REPORT_TOOL = "rapporter"
UsageCallback = Callable[[int, int], None]


class AgentError(RuntimeError):
    """Un agent n'a pas pu rendre de rapport."""


def make_client():
    import anthropic

    return anthropic.Anthropic(max_retries=3)


def create_message(client, **kwargs):
    """Appel Messages API (bêta, pour le repli automatique en cas de refus)."""
    betas = list(kwargs.pop("betas", []))
    if config.USE_FALLBACKS:
        betas.append(config.FALLBACK_BETA)
        kwargs["fallbacks"] = "default"
    if betas:
        kwargs["betas"] = betas
    return client.beta.messages.create(**kwargs)


def usage_tokens(response) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    tokens_in = sum(
        int(getattr(usage, name, 0) or 0)
        for name in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    )
    return tokens_in, int(getattr(usage, "output_tokens", 0) or 0)


def text_of(content) -> str:
    return "\n".join(getattr(b, "text", "") for b in content if getattr(b, "type", None) == "text").strip()


def extract_json(text: str) -> dict | None:
    """Récupère un objet JSON dans un texte libre (bloc ```json``` ou premier {...})."""
    if not text:
        return None
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def web_tools(spec: AgentSpec) -> list[dict]:
    tools: list[dict] = []
    if spec.web_search_uses:
        tools.append({
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": spec.web_search_uses,
            "user_location": {"type": "approximate", "country": "FR", "timezone": "Europe/Paris"},
        })
    if spec.web_fetch_uses:
        tools.append({
            "type": "web_fetch_20260209",
            "name": "web_fetch",
            "max_uses": spec.web_fetch_uses,
            "max_content_tokens": 20000,
        })
    return tools


def report_tool(spec: AgentSpec) -> dict:
    return {
        "name": REPORT_TOOL,
        "description": "Rendre ton rapport final au chef d'équipe. À appeler une seule fois, quand ton travail est terminé.",
        "input_schema": spec.rapport_schema,
    }


def run_specialist(
    client,
    spec: AgentSpec,
    consigne: str,
    contexte: dict[str, Any],
    on_usage: UsageCallback | None = None,
    max_turns: int = 8,
) -> dict:
    """Fait travailler un agent jusqu'à ce qu'il appelle `rapporter`. Renvoie le rapport (dict)."""
    tools = [*web_tools(spec), report_tool(spec)]
    messages: list[dict] = [{
        "role": "user",
        "content": (
            "Contexte (JSON) :\n"
            + json.dumps(contexte, ensure_ascii=False, indent=1, default=str)
            + f"\n\nConsigne du chef d'équipe :\n{consigne}"
        ),
    }]
    nudged = False
    for _ in range(max_turns):
        response = create_message(
            client,
            model=config.AGENT_MODEL,
            max_tokens=16000,
            system=spec.system,
            tools=tools,
            messages=messages,
            output_config={"effort": spec.effort},
            cache_control={"type": "ephemeral"},
        )
        if on_usage:
            on_usage(*usage_tokens(response))
        if response.stop_reason == "refusal":
            raise AgentError(f"{spec.nom} : la requête a été refusée par le modèle.")

        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        for block in tool_uses:
            if block.name == REPORT_TOOL:
                report = block.input if isinstance(block.input, dict) else {}
                return report

        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "pause_turn":
            continue
        if tool_uses:
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                 "content": f"Outil inconnu : {b.name}. Utilise `{REPORT_TOOL}` pour rendre ton rapport."}
                for b in tool_uses
            ]})
            continue

        parsed = extract_json(text_of(response.content))
        if parsed is not None:
            return parsed
        if nudged:
            break
        nudged = True
        messages.append({"role": "user", "content": f"Rends maintenant ton rapport en appelant l'outil `{REPORT_TOOL}`."})

    raise AgentError(f"{spec.nom} n'a pas rendu de rapport.")
