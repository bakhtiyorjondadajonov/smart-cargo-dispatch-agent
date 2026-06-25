"""Gemini-powered ranking — the decision-making 'brain' of the agent.

Given a request and a short list of pre-filtered candidate vehicles, Gemini
picks the single best vehicle and justifies the choice. We use structured JSON
output so the result is machine-readable and grounded in the candidate ids we
actually passed in.

If the API key is missing or the call fails, callers fall back to the
deterministic nearest candidate so the pipeline never stalls (see pipeline.py).
"""
from __future__ import annotations

import json
import logging
import time

from pydantic import BaseModel

from app.agent.candidates import Candidate
from app.config import settings
from app.models import Zaproslar

logger = logging.getLogger(__name__)


class GeminiVerdict(BaseModel):
    best_mashina_id: int
    score: float          # 0..1 confidence / suitability
    reasoning: str


class GeminiUnavailable(RuntimeError):
    """Raised when Gemini cannot be used (no key, import error, API failure)."""


def _build_prompt(zapros: Zaproslar, candidates: list[Candidate]) -> str:
    lines = [
        "You are a logistics dispatcher AI. A new cargo transport request arrived.",
        "Pick the single BEST vehicle to assign from the candidate list.",
        "Prefer vehicles closest to the pickup location; consider how far each is.",
        "",
        "REQUEST:",
        f"  pickup: {zapros.yuk_ortish_joyi}",
        f"  dropoff: {zapros.yuk_tushirish_joyi}",
        f"  load_date: {zapros.yuklash_sanasi}",
        f"  location_mode: {zapros.location_type}",
        "",
        "CANDIDATE VEHICLES (choose best_mashina_id ONLY from these ids):",
    ]
    for c in candidates:
        lines.append(
            f"  - id={c.mashina.id} plate={c.mashina.mashina_raqami} "
            f"location={c.mashina.joriy_lokatsiya} ({c.distance_label})"
        )
    lines += [
        "",
        "Return JSON: best_mashina_id (one of the ids above), "
        "score (0..1 suitability), reasoning (one short sentence).",
    ]
    return "\n".join(lines)


def rank_with_gemini(zapros: Zaproslar, candidates: list[Candidate]) -> GeminiVerdict:
    if not settings.gemini_api_key:
        raise GeminiUnavailable("GEMINI_API_KEY not set")
    if not candidates:
        raise GeminiUnavailable("no candidates to rank")

    try:
        from google import genai
        from google.genai import types
    except ImportError as e:  # pragma: no cover
        raise GeminiUnavailable(f"google-genai not installed: {e}") from e

    valid_ids = {c.mashina.id for c in candidates}
    prompt = _build_prompt(zapros, candidates)

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=GeminiVerdict,
        temperature=0.2,
        # Disable "thinking" for this latency-sensitive pick-nearest task.
        thinking_config=types.ThinkingConfig(
            thinking_budget=settings.gemini_thinking_budget
        ),
    )

    client = genai.Client(api_key=settings.gemini_api_key)
    resp = _generate_with_retry(client, prompt, config)
    verdict = _parse_response(resp)
    if verdict.best_mashina_id not in valid_ids:
        # Model hallucinated an id outside the candidate set — reject and fall back.
        raise GeminiUnavailable(
            f"Gemini returned out-of-set id {verdict.best_mashina_id}"
        )
    return verdict


def _generate_with_retry(client, prompt: str, config):
    """Call Gemini with bounded exponential backoff on transient errors.

    Retries up to settings.gemini_max_retries; on final failure raises
    GeminiUnavailable so the caller falls back to the nearest candidate.
    """
    attempts = max(1, settings.gemini_max_retries + 1)
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return client.models.generate_content(
                model=settings.gemini_model, contents=prompt, config=config
            )
        except Exception as e:  # network / quota / SDK error
            last_err = e
            if i < attempts - 1:
                backoff = 0.5 * (2 ** i)
                logger.warning("Gemini call failed (attempt %d/%d): %s; retrying in %.1fs",
                               i + 1, attempts, e, backoff)
                time.sleep(backoff)
    raise GeminiUnavailable(f"Gemini API call failed after {attempts} attempt(s): {last_err}")


def _parse_response(resp) -> GeminiVerdict:
    parsed = getattr(resp, "parsed", None)
    if isinstance(parsed, GeminiVerdict):
        return parsed
    text = getattr(resp, "text", None)
    if not text:
        raise GeminiUnavailable("empty Gemini response")
    try:
        return GeminiVerdict(**json.loads(text))
    except Exception as e:  # pragma: no cover
        raise GeminiUnavailable(f"could not parse Gemini response: {e}") from e
