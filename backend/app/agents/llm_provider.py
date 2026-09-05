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

from app.config import get_settings

logger = logging.getLogger("finrecon.llm")


class LLMUnavailableError(Exception):
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
            f"Unsupported LLM_PROVIDER: "
            f"{self.settings.LLM_PROVIDER}"
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

        client = anthropic.Anthropic(
            api_key=self.settings.ANTHROPIC_API_KEY,
            timeout=self.settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )

        last_error = None

        for attempt in range(2):

            try:

                response = client.messages.create(
                    model=self.settings.LLM_MODEL,
                    max_tokens=4000,
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

        # -----------------------------------------------------
        # IMPORTANT
        #
        # We give Gemini enough output space.
        #
        # Previously 1200 tokens was being reached and Gemini
        # returned incomplete JSON with:
        #
        # FinishReason.MAX_TOKENS
        #
        # We also explicitly inspect finish_reason BEFORE trying
        # to parse the JSON.
        # -----------------------------------------------------

        prompt = f"""
You are FinRecon AI, a financial reconciliation investigation assistant.

SYSTEM INSTRUCTIONS:
{system_prompt}

INVESTIGATION DATA:
{user_prompt}

Your task is to investigate the financial exception.

Return ONLY ONE valid JSON object.

Use EXACTLY this structure:

{{
  "root_cause": "short explanation",
  "confidence": 0.90,
  "recommendation": "short recommended action",
  "evidence": [
    "short evidence 1",
    "short evidence 2"
  ],
  "explanation": "short explanation"
}}

STRICT RULES:

1. Return JSON only.
2. Do not use Markdown.
3. Do not use code fences.
4. Do not write anything before the JSON.
5. Do not write anything after the JSON.
6. Use double quotes.
7. confidence must be a number between 0 and 1.
8. Maximum 2 evidence items.
9. Keep every string concise.
10. Do not invent financial facts.
11. Use only information present in the investigation data.
12. Make sure the JSON is completely closed.
"""

        last_error = None

        # -----------------------------------------------------
        # First attempt
        # -----------------------------------------------------

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

                        # IMPORTANT:
                        # Give the model substantially more room
                        # than the previous 1200-token limit.
                        max_output_tokens=4096,

                        response_mime_type="application/json",
                    ),
                )

                text = (response.text or "").strip()

                logger.info(
                    "Gemini response received, length=%s",
                    len(text),
                )

                # -------------------------------------------------
                # Read finish reason BEFORE parsing.
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
                # If Gemini explicitly says MAX_TOKENS, the JSON
                # is potentially incomplete.
                #
                # DO NOT attempt to parse it.
                # Retry with an ultra-compact schema.
                # -------------------------------------------------

                if self._is_max_tokens_reason(
                    finish_reason
                ):

                    logger.warning(
                        "Gemini response was truncated by "
                        "MAX_TOKENS. Retrying with "
                        "ultra-compact JSON."
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

                # -------------------------------------------------
                # Empty response
                # -------------------------------------------------

                if not text:

                    raise ValueError(
                        "Gemini returned an empty response"
                    )

                # -------------------------------------------------
                # Parse only after confirming response was not
                # truncated.
                # -------------------------------------------------

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

                # -------------------------------------------------
                # If this was the first attempt, retry using an
                # ultra-compact prompt.
                #
                # This catches both:
                # - MAX_TOKENS
                # - malformed/truncated JSON
                # -------------------------------------------------

                if attempt == 0:

                    logger.warning(
                        "Retrying Gemini with "
                        "ultra-compact JSON prompt."
                    )

                    prompt = self._build_compact_prompt(
                        system_prompt,
                        user_prompt,
                    )

        raise LLMUnavailableError(
            f"Gemini did not return valid JSON: {last_error}"
        )

    # =========================================================
    # COMPACT GEMINI PROMPT
    # =========================================================

    @staticmethod
    def _build_compact_prompt(
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        return f"""
You are investigating a financial reconciliation exception.

SYSTEM:
{system_prompt}

DATA:
{user_prompt}

Return ONLY valid JSON.

Use exactly:

{{
  "root_cause": "short",
  "confidence": 0.9,
  "recommendation": "short",
  "evidence": ["short"],
  "explanation": "short"
}}

Rules:
- JSON only.
- No Markdown.
- No code fences.
- Maximum ONE evidence item.
- Keep every string under 20 words.
- Do not invent facts.
- Use only the supplied data.
- Close the JSON completely.
"""

    # =========================================================
    # FINISH REASON CHECK
    # =========================================================

    @staticmethod
    def _is_max_tokens_reason(
        finish_reason,
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
        # Remove Markdown fences.
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
        # Normal JSON parsing.
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
        # Try extracting a complete JSON object.
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
        # Try escaped JSON.
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

            # Inside a JSON string
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

            # Start JSON string
            if char == '"':
                in_string = True
                continue

            # Opening object
            if char == "{":
                depth += 1
                continue

            # Closing object
            if char == "}":

                depth -= 1

                if depth == 0:

                    return text[
                        start:index + 1
                    ]

        # Object was never closed.
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