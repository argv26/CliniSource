"""Pre-Step Clinical Planning Engine (AttendingPlanner)."""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from dotenv import load_dotenv

from agent.prompts import PLANNER_SYSTEM_INSTRUCTION

load_dotenv()


@dataclass
class ClinicalPlan:
    """Structured pre-retrieval clinical reasoning plan."""
    diagnostic_hypotheses: list[str] = field(default_factory=list)
    organ_systems: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    evidence_checklist: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AttendingPlanner:
    """Formulates diagnostic strategy and targeted textbook search queries before retrieval."""

    def __init__(
        self,
        api_key: str | None = None,
        openai_api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get(
            "GEMINI_PLANNER_MODEL",
            os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        )

    def plan(
        self,
        user_message: str,
        book_catalog: list[dict[str, Any]] | None = None,
        active_books: list[str] | None = None,
    ) -> ClinicalPlan:
        """Generates a structured clinical plan for a medical query.

        Raises:
            RuntimeError: If neither GEMINI_API_KEY nor OPENAI_API_KEY is configured,
                         or if LLM generation fails.
        """
        if not self.api_key and not self.openai_api_key:
            raise RuntimeError("LLM API key not configured for AttendingPlanner")

        prompt_content = f"User Inquiry: {user_message.strip()}"
        if active_books:
            prompt_content += f"\nActive Textbook Scope: {', '.join(active_books)}"

        # 1. Try Gemini Client if API key is present
        if self.api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key)
                candidate_models = [
                    self.model,
                    "gemini-3.5-flash-lite",
                    "gemini-3.1-flash-lite",
                    "gemini-3.5-flash",
                ]
                seen = set()
                models = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

                last_error: Exception | None = None
                for m in models:
                    try:
                        response = client.models.generate_content(
                            model=m,
                            contents=prompt_content,
                            config=types.GenerateContentConfig(
                                system_instruction=PLANNER_SYSTEM_INSTRUCTION,
                                response_mime_type="application/json",
                                temperature=0.1,
                            ),
                        )
                        if response and response.text:
                            return self._parse_plan_json(response.text, fallback_query=user_message)
                    except Exception as me:
                        last_error = me
                        continue

                if last_error:
                    print(f"[AttendingPlanner] Gemini models failed: {last_error}")
            except Exception as e:
                print(f"[AttendingPlanner] Gemini execution error: {e}")

        # 2. Try OpenAI if API key is present and Gemini didn't complete
        if self.openai_api_key:
            try:
                import openai

                client = openai.OpenAI(api_key=self.openai_api_key)
                response = client.chat.completions.create(
                    model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
                    messages=[
                        {"role": "system", "content": PLANNER_SYSTEM_INSTRUCTION},
                        {"role": "user", "content": prompt_content},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                text = response.choices[0].message.content or "{}"
                return self._parse_plan_json(text, fallback_query=user_message)
            except Exception as e:
                raise RuntimeError(f"AttendingPlanner OpenAI execution failed: {e}")

        raise RuntimeError("AttendingPlanner failed to generate plan with available LLM providers")

    def _parse_plan_json(self, raw_text: str, fallback_query: str) -> ClinicalPlan:
        """Parses LLM JSON string into a structured ClinicalPlan."""
        cleaned = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"```$", "", cleaned.strip()).strip()

        try:
            data = json.loads(cleaned)
        except Exception:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception:
                    data = {}
            else:
                data = {}

        search_queries = data.get("search_queries")
        if not search_queries or not isinstance(search_queries, list):
            clean_fallback = re.sub(r"[^\w\s-]", " ", fallback_query).strip()
            search_queries = [clean_fallback] if clean_fallback else []

        return ClinicalPlan(
            diagnostic_hypotheses=data.get("diagnostic_hypotheses") or [],
            organ_systems=data.get("organ_systems") or [],
            search_queries=[str(q).strip() for q in search_queries if str(q).strip()],
            evidence_checklist=data.get("evidence_checklist") or [],
        )

