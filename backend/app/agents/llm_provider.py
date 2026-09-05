"""
LLM provider abstraction for FinRecon AI.

Supports:
- Anthropic
- Google Gemini

The application degrades gracefully when no LLM is configured.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import get_settings

logger = logging.getLogger("finrecon.llm")


class LLMUnavailableError(Exception):
    """Raised when the configured LLM cannot be used."""
    pass


class LLMProvider:
    def __init__(self):
        self.settings = get_settings()

    # =========================================================
    # PUBLIC API
    # =========================================================

    def is_available(self) -> bool:
        return self.settings.llm_configured

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:
        """
        Call the configured LLM and return a parsed JSON object.
        """

        if not self.is_available():
            raise LLMUnavailableError(
                "No LLM provider configured"
            )

        provider = self.settings.LLM_PROVIDER.lower().strip()

        if provider == "anthropic":
            return self._call_anthropic(
                system_prompt,
                user_prompt,
            )

        if provider == "gemini":
            return self._call_gemini(
                system_prompt,
                user_prompt,
            )

        raise LLMUnavailableError(
            f"Unsupported LLM_PROVIDER: {self.settings.LLM_PROVIDER}"
        )

    # =========================================================
    # ANTHROPIC
    # =========================================================

    def _call_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:

        try:
            import anthropic
        except ImportError as exc:
            raise LLMUnavailableError(
                "Anthropic package is not installed"
            ) from exc

        if not self.settings.ANTHROPIC_API_KEY:
            raise LLMUnavailableError(
                "ANTHROPIC_API_KEY is not configured"
            )

        client = anthropic.Anthropic(
            api_key=self.settings.ANTHROPIC_API_KEY,
            timeout=self.settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )

        last_error: Exception | None = None

        for attempt in range(2):

            try:

                response = client.messages.create(
                    model=self.settings.LLM_MODEL,
                    max_tokens=2000,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": user_prompt,
                        }
                    ],
                )

                text = "".join(
                    block.text
                    for block in response.content
                    if getattr(block, "type", None) == "text"
                ).strip()

                logger.info(
                    "Anthropic response received, length=%s",
                    len(text),
                )

                return self._parse_json(text)

            except Exception as exc:

                last_error = exc

                logger.warning(
                    "Anthropic call/parse failed "
                    "(attempt %s): %s",
                    attempt + 1,
                    exc,
                )

        raise LLMUnavailableError(
            f"Anthropic did not return valid JSON: {last_error}"
        )

    # =========================================================
    # GEMINI
    # =========================================================

    def _call_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise LLMUnavailableError(
                "Google GenAI package is not installed"
            ) from exc

        if not self.settings.GEMINI_API_KEY:
            raise LLMUnavailableError(
                "GEMINI_API_KEY is not configured"
            )

        client = genai.Client(
            api_key=self.settings.GEMINI_API_KEY
        )

        last_error: Exception | None = None

        prompt = self._build_gemini_prompt(
            system_prompt,
            user_prompt,
        )

        for attempt in range(2):

            try:

                logger.info(
                    "Calling Gemini model: %s (attempt %s)",
                    self.settings.LLM_MODEL,
                    attempt + 1,
                )

                response = client.models.generate_content(
                    model=self.settings.LLM_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=2048,
                        response_mime_type="application/json",
                    ),
                )

                text = (response.text or "").strip()

                logger.info(
                    "Gemini response received, length=%s",
                    len(text),
                )

                # -------------------------------------------------
                # Finish reason
                # -------------------------------------------------

                finish_reason = None

                try:

                    if response.candidates:

                        candidate = response.candidates[0]

                        finish_reason = getattr(
                            candidate,
                            "finish_reason",
                            None,
                        )

                        logger.info(
                            "Gemini finish reason: %s",
                            finish_reason,
                        )

                except Exception as exc:

                    logger.debug(
                        "Could not read Gemini finish reason: %s",
                        exc,
                    )

                # -------------------------------------------------
                # If truncated, retry with compact prompt.
                # -------------------------------------------------

                if self._is_max_tokens_reason(
                    finish_reason
                ):

                    logger.warning(
                        "Gemini response reached MAX_TOKENS."
                    )

                    if attempt == 0:

                        prompt = self._build_compact_prompt(
                            system_prompt,
                            user_prompt,
                        )

                        continue

                    raise ValueError(
                        "Gemini repeatedly stopped at MAX_TOKENS"
                    )

                if not text:
                    raise ValueError(
                        "Gemini returned an empty response"
                    )

                result = self._parse_json(text)

                logger.info(
                    "Gemini investigation successfully parsed."
                )

                return result

            except Exception as exc:

                last_error = exc

                logger.warning(
                    "Gemini call/parse failed "
                    "(attempt %s): %s",
                    attempt + 1,
                    exc,
                )

                if attempt == 0:

                    logger.warning(
                        "Retrying Gemini with compact JSON prompt."
                    )

                    prompt = self._build_compact_prompt(
                        system_prompt,
                        user_prompt,
                    )

                    continue

        raise LLMUnavailableError(
            f"Gemini did not return valid JSON: {last_error}"
        )

    # =========================================================
    # GEMINI PROMPTS
    # =========================================================

    @staticmethod
    def _build_gemini_prompt(
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        return f"""
You are FinRecon AI, a financial reconciliation investigation assistant.

SYSTEM INSTRUCTIONS:
{system_prompt}

INVESTIGATION DATA:
{user_prompt}

Your task is to investigate the already-detected financial exception.

Return ONLY ONE valid JSON object.

The JSON MUST contain EXACTLY these fields:

{{
  "exception_type": "string",
  "root_cause": "short explanation",
  "evidence": ["short evidence 1", "short evidence 2"],
  "financial_impact": 0,
  "confidence": 0.90,
  "recommended_action": "short recommended action",
  "requires_human_approval": true,
  "explanation": "short explanation"
}}

STRICT RULES:

1. Return JSON only.
2. Do not use Markdown.
3. Do not use ``` fences.
4. Do not write anything before the JSON.
5. Do not write anything after the JSON.
6. Use double quotes.
7. confidence must be between 0 and 1.
8. financial_impact must be a number.
9. requires_human_approval must be true or false.
10. evidence must be an array of strings.
11. Maximum 2 evidence items.
12. Keep all strings concise.
13. Do not invent financial facts.
14. Use ONLY information contained in the investigation data.
15. recommended_action must be a safe recommendation, not an automatic financial change.
16. Make sure the JSON is completely closed.

Return the JSON object now.
"""

    @staticmethod
    def _build_compact_prompt(
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        return f"""
You are investigating one financial reconciliation exception.

SYSTEM:
{system_prompt}

DATA:
{user_prompt}

Return ONLY valid JSON.

Use exactly:

{{
  "exception_type": "type",
  "root_cause": "short",
  "evidence": ["short"],
  "financial_impact": 0,
  "confidence": 0.9,
  "recommended_action": "short",
  "requires_human_approval": true,
  "explanation": "short"
}}

Rules:
- JSON only.
- No Markdown.
- No code fences.
- Maximum ONE evidence item.
- Keep strings very short.
- financial_impact must be a number.
- confidence must be between 0 and 1.
- requires_human_approval must be true or false.
- Do not invent facts.
- Use only supplied data.
- Close the JSON completely.
"""

    # =========================================================
    # FINISH REASON
    # =========================================================

    @staticmethod
    def _is_max_tokens_reason(
        finish_reason: Any,
    ) -> bool:

        if finish_reason is None:
            return False

        value = str(
            finish_reason
        ).upper()

        return (
            "MAX_TOKENS" in value
            or "MAX TOKEN" in value
        )

    # =========================================================
    # JSON PARSER
    # =========================================================

    @staticmethod
    def _parse_json(
        text: str,
    ) -> dict:

        if not text:
            raise ValueError(
                "LLM returned an empty response"
            )

        text = text.strip()

        # -----------------------------------------------------
        # Remove Markdown fences if present.
        # -----------------------------------------------------

        if text.startswith("```"):

            text = re.sub(
                r"^```(?:json)?\s*",
                "",
                text,
                flags=re.IGNORECASE,
            )

            text = re.sub(
                r"\s*```$",
                "",
                text,
            )

            text = text.strip()

        # -----------------------------------------------------
        # First attempt: entire response.
        # -----------------------------------------------------

        try:

            result = json.loads(text)

            if not isinstance(result, dict):
                raise ValueError(
                    "LLM response is not a JSON object"
                )

            return result

        except json.JSONDecodeError as exc:

            logger.warning(
                "Initial JSON parsing failed: %s",
                exc,
            )

        # -----------------------------------------------------
        # Second attempt: balanced JSON extraction.
        # -----------------------------------------------------

        candidate = LLMProvider._extract_json_object(
            text
        )

        if candidate:

            try:

                result = json.loads(candidate)

                if isinstance(result, dict):
                    return result

            except json.JSONDecodeError as exc:

                logger.warning(
                    "Extracted JSON parsing failed: %s",
                    exc,
                )

        # -----------------------------------------------------
        # Third attempt: escaped JSON.
        # -----------------------------------------------------

        try:

            cleaned = text.replace(
                "\\n",
                " ",
            )

            cleaned = cleaned.replace(
                "\\r",
                " ",
            )

            cleaned = cleaned.replace(
                "\\t",
                " ",
            )

            result = json.loads(cleaned)

            if isinstance(result, dict):
                return result

        except Exception:
            pass

        raise ValueError(
            "Unable to parse LLM response as JSON. "
            f"Response preview: {text[:1000]}"
        )

    # =========================================================
    # BALANCED JSON EXTRACTION
    # =========================================================

    @staticmethod
    def _extract_json_object(
        text: str,
    ) -> str | None:

        start = text.find("{")

        if start == -1:
            return None

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start,
            len(text),
        ):

            char = text[index]

            if in_string:

                if escaped:

                    escaped = False
                    continue

                if char == "\\":
                    escaped = True
                    continue

                if char == '"':
                    in_string = False

                continue

            if char == '"':

                in_string = True
                continue

            if char == "{":

                depth += 1
                continue

            if char == "}":

                depth -= 1

                if depth == 0:

                    return text[
                        start:index + 1
                    ]

        return None


# =============================================================
# SINGLETON
# =============================================================

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:

    global _provider

    if _provider is None:
        _provider = LLMProvider()

    return _provider
