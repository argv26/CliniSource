"""LLM-as-a-Judge and deterministic offline heuristic evaluators for faithfulness, completeness, and soundness."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv

from agent.telemetry import extract_gemini_usage, extract_openai_usage
from evals.schema import EvalCase, MetricResult

load_dotenv()

_STOPWORDS = {
    "about", "above", "after", "against", "also", "although", "among", "another",
    "because", "before", "being", "between", "both", "causes", "clinical", "common",
    "could", "criteria", "defined", "describe", "does", "during", "each", "either",
    "explain", "first", "following", "from", "have", "having", "however", "include",
    "includes", "including", "indicated", "initial", "into", "level", "levels",
    "major", "management", "most", "must", "normal", "other", "patient", "patients",
    "presents", "primary", "required", "requires", "serum", "should", "signs",
    "since", "some", "such", "than", "that", "their", "them", "then", "there",
    "these", "they", "this", "those", "through", "treatment", "typically", "under",
    "used", "using", "usually", "what", "when", "where", "which", "while", "with",
    "without", "workup", "would",
}

_OOS_HONESTY_PHRASES = (
    "not found",
    "couldn't find",
    "could not find",
    "not covered",
    "no matching",
    "not in the indexed",
    "do not contain",
    "does not contain",
    "outside the scope",
    "cannot verify",
    "unable to find",
    "no relevant",
)

_JUDGE_SYSTEM_PROMPT = """You are a strict Medical & Academic RAG Evaluation Judge.
Grade the Assistant Reply strictly against the provided Retrieved Textbook Passages and Expected Answer Points.

Rubric (integer 1 to 5):
1. faithfulness (1-5):
   - 5: Every factual claim, cutoff, mechanism, and dosage in the reply is directly supported by the Retrieved Textbook Passages (or, if out-of-scope with empty passages, honestly states the library lacks the topic).
   - 3: Mostly supported, with minor unverified phrasing or mild extrapolation.
   - 1: Contains fabricated facts, hallucinated numbers/thresholds, or contradicts the retrieved passages.
2. answer_completeness (1-5):
   - 5: Directly answers the query and covers all Expected Answer Points clearly.
   - 3: Partially answers the query, missing one or more major Expected Answer Points.
   - 1: Fails to address the query or misses nearly all Expected Answer Points.
3. clinical_soundness (1-5):
   - 5: Medically/academically accurate, safe, clear, and free of dangerous errors.
   - 3: Acceptable overall but imprecise or incomplete on important clinical caveats.
   - 1: Contains clinically unsafe, misleading, or contradictory statements.

Respond STRICTLY in valid JSON matching:
{
  "faithfulness": {"score": 5, "rationale": "short reason"},
  "answer_completeness": {"score": 5, "rationale": "short reason"},
  "clinical_soundness": {"score": 5, "rationale": "short reason"}
}"""


def _normalize_1_to_5(raw_score: int | float) -> float:
    """Maps a 1..5 rubric integer smoothly onto [0.0, 1.0] (1->0.0, 3->0.5, 5->1.0)."""
    clamped = max(1.0, min(5.0, float(raw_score)))
    return round((clamped - 1.0) / 4.0, 4)


def _strip_followups(text: str) -> str:
    if "[FOLLOW_UP_QUESTIONS]" in text:
        return text.split("[FOLLOW_UP_QUESTIONS]", 1)[0].strip()
    return text.strip()


def _content_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _numeric_tokens(text: str) -> set[str]:
    # Strip citation pills [1], [2] before extracting clinical numbers
    cleaned = re.sub(r"\[\d+\]", "", text)
    return set(re.findall(r"\b\d+(?:\.\d+)?\b", cleaned))


def _ratio_to_rubric(ratio: float) -> int:
    if ratio >= 0.60:
        return 5
    if ratio >= 0.42:
        return 4
    if ratio >= 0.25:
        return 3
    if ratio >= 0.12:
        return 2
    return 1


class LLMJudgeEvaluator:
    """Evaluates faithfulness, answer completeness, and clinical soundness in live or offline mode."""

    PASS_THRESHOLD = 0.75  # >= 4/5 on normalized [0, 1] scale

    def __init__(
        self,
        mode: str = "offline",
        gemini_api_key: str | None = None,
        openai_api_key: str | None = None,
        model: str | None = None,
    ):
        if mode not in ("offline", "live"):
            raise ValueError(f"Invalid LLMJudgeEvaluator mode '{mode}'. Use 'offline' or 'live'.")
        self.mode = mode
        self.gemini_api_key = gemini_api_key if gemini_api_key is not None else os.environ.get("GEMINI_API_KEY")
        self.openai_api_key = openai_api_key if openai_api_key is not None else os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("EVAL_JUDGE_MODEL", "gemini-3.5-flash-lite")
        self.last_judge_telemetry: dict[str, Any] = {}

    def evaluate(
        self,
        case: EvalCase,
        reply: str,
        retrieved_chunks: list[dict[str, Any]],
    ) -> dict[str, MetricResult]:
        """Scores faithfulness, answer_completeness, and clinical_soundness for a case."""
        self.last_judge_telemetry = {}

        if case.is_conversational:
            note = {"mode": self.mode, "raw_score": 5, "rationale": "Skipped on conversational fast-path."}
            return {
                "faithfulness": MetricResult("faithfulness", 1.0, True, note),
                "answer_completeness": MetricResult("answer_completeness", 1.0, True, note),
                "clinical_soundness": MetricResult("clinical_soundness", 1.0, True, note),
            }

        if self.mode == "offline":
            return self._evaluate_offline(case, reply, retrieved_chunks)

        return self._evaluate_live(case, reply, retrieved_chunks)

    def _evaluate_offline(
        self,
        case: EvalCase,
        reply: str,
        retrieved_chunks: list[dict[str, Any]],
    ) -> dict[str, MetricResult]:
        main_reply = _strip_followups(reply or "")
        if not main_reply:
            empty_details = {"mode": "offline", "raw_score": 1, "rationale": "Empty reply."}
            return {
                "faithfulness": MetricResult("faithfulness", 0.0, False, empty_details),
                "answer_completeness": MetricResult("answer_completeness", 0.0, False, empty_details),
                "clinical_soundness": MetricResult("clinical_soundness", 0.0, False, empty_details),
            }

        lower_reply = main_reply.lower()

        if case.is_out_of_scope:
            disclosed = any(p in lower_reply for p in _OOS_HONESTY_PHRASES)
            raw_score = 5 if disclosed else 1
            norm = _normalize_1_to_5(raw_score)
            rationale = (
                "Honestly disclosed missing coverage in indexed textbooks."
                if disclosed
                else "Did not disclose out-of-scope limitation; risk of hallucination."
            )
            details = {"mode": "offline", "raw_score": raw_score, "rationale": rationale}
            return {
                "faithfulness": MetricResult("faithfulness", norm, disclosed, details),
                "answer_completeness": MetricResult("answer_completeness", norm, disclosed, details),
                "clinical_soundness": MetricResult("clinical_soundness", norm, disclosed, details),
            }

        # 1. Faithfulness: overlap of reply content tokens & numbers with retrieved chunks
        evidence_text = "\n".join(
            f"{c.get('heading_path', '')} {c.get('text', '')}"
            for c in (retrieved_chunks or [])
        )
        reply_tokens = _content_tokens(main_reply)
        evidence_tokens = _content_tokens(evidence_text)

        if not evidence_tokens:
            faith_raw = 1
            faith_rationale = "No retrieved textbook evidence available to support claims."
            overlap_ratio = 0.0
            significant_ungrounded: list[str] = []
        else:
            overlap = reply_tokens & evidence_tokens
            overlap_ratio = len(overlap) / max(len(reply_tokens), 1)

            reply_nums = _numeric_tokens(main_reply)
            evidence_nums = _numeric_tokens(evidence_text)
            ungrounded_nums = sorted(reply_nums - evidence_nums)

            # Penalize ungrounded clinical numbers (excluding ordinary small list indices 1-5)
            significant_ungrounded = [n for n in ungrounded_nums if n not in {"1", "2", "3", "4", "5"}]
            penalty = min(3, len(significant_ungrounded))
            faith_raw = max(1, _ratio_to_rubric(overlap_ratio) - penalty)
            faith_rationale = (
                f"Token grounding overlap={overlap_ratio:.2f}; "
                f"ungrounded numbers={significant_ungrounded or 'none'}."
            )

        faith_norm = _normalize_1_to_5(faith_raw)
        faith_result = MetricResult(
            name="faithfulness",
            score=faith_norm,
            passed=faith_norm >= self.PASS_THRESHOLD,
            details={
                "mode": "offline",
                "raw_score": faith_raw,
                "token_overlap_ratio": round(overlap_ratio, 3),
                "ungrounded_numbers": significant_ungrounded,
                "rationale": faith_rationale,
            },
        )

        # 2. Answer completeness: coverage of expected_answer_points
        points = list(case.expected_answer_points or [])
        if not points:
            comp_raw = 5 if len(main_reply) >= 60 else 2
            comp_ratio = 1.0 if len(main_reply) >= 60 else 0.25
            covered_points = 0
        else:
            reply_all_tokens = _content_tokens(main_reply) | _numeric_tokens(main_reply)
            point_scores: list[float] = []
            covered_points = 0
            for pt in points:
                pt_tokens = _content_tokens(pt) | _numeric_tokens(pt)
                if not pt_tokens:
                    point_scores.append(1.0)
                    covered_points += 1
                    continue
                pt_cov = len(pt_tokens & reply_all_tokens) / len(pt_tokens)
                point_scores.append(pt_cov)
                if pt_cov >= 0.40:
                    covered_points += 1
            comp_ratio = sum(point_scores) / len(point_scores)
            comp_raw = _ratio_to_rubric(comp_ratio)

        comp_norm = _normalize_1_to_5(comp_raw)
        comp_result = MetricResult(
            name="answer_completeness",
            score=comp_norm,
            passed=comp_norm >= self.PASS_THRESHOLD,
            details={
                "mode": "offline",
                "raw_score": comp_raw,
                "covered_points": covered_points,
                "total_points": len(points),
                "mean_point_coverage": round(comp_ratio, 3),
                "rationale": f"Covered {covered_points}/{len(points)} expected answer points (coverage={comp_ratio:.2f}).",
            },
        )

        # 3. Clinical soundness: weighted toward faithfulness and capped to avoid hallucinated answers passing
        weighted = round(0.6 * faith_raw + 0.4 * comp_raw)
        sound_raw = max(1, min(5, min(weighted, faith_raw + 1)))
        sound_norm = _normalize_1_to_5(sound_raw)
        sound_result = MetricResult(
            name="clinical_soundness",
            score=sound_norm,
            passed=sound_norm >= self.PASS_THRESHOLD,
            details={
                "mode": "offline",
                "raw_score": sound_raw,
                "rationale": f"Offline heuristic soundness derived from faithfulness={faith_raw}/5 and completeness={comp_raw}/5.",
            },
        )

        return {
            "faithfulness": faith_result,
            "answer_completeness": comp_result,
            "clinical_soundness": sound_result,
        }

    def _build_judge_prompt(
        self,
        case: EvalCase,
        reply: str,
        retrieved_chunks: list[dict[str, Any]],
    ) -> str:
        passages_block = []
        for idx, c in enumerate((retrieved_chunks or [])[:6], start=1):
            heading = str(c.get("heading_path") or "")
            book = str(c.get("book_slug") or "")
            page = c.get("page_start", "")
            snippet = str(c.get("text") or "").strip()[:1200]
            passages_block.append(f"[{idx}] ({book}, p.{page}, {heading}):\n{snippet}")

        passages_str = "\n\n".join(passages_block) if passages_block else "(No textbook passages retrieved)"
        points_str = "\n".join(f"- {p}" for p in case.expected_answer_points) or "- None specified"

        return (
            f"Case ID: {case.id}\n"
            f"Category: {case.category} (out_of_scope={case.is_out_of_scope})\n"
            f"User Query: {case.query}\n\n"
            f"Expected Answer Points:\n{points_str}\n\n"
            f"Retrieved Textbook Passages:\n{passages_str}\n\n"
            f"Assistant Reply:\n{_strip_followups(reply or '')}\n"
        )

    def _parse_judge_json(self, raw_text: str) -> dict[str, MetricResult]:
        cleaned = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"```$", "", cleaned.strip()).strip()

        try:
            data = json.loads(cleaned)
        except Exception:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                raise ValueError(f"Judge returned unparseable non-JSON text: {raw_text[:200]}")
            data = json.loads(match.group(0))

        metrics: dict[str, MetricResult] = {}
        for key in ("faithfulness", "answer_completeness", "clinical_soundness"):
            entry = data.get(key)
            if isinstance(entry, dict):
                raw_score = int(max(1, min(5, round(float(entry.get("score", 1))))))
                rationale = str(entry.get("rationale") or "")
            elif isinstance(entry, (int, float)):
                raw_score = int(max(1, min(5, round(float(entry)))))
                rationale = ""
            else:
                raise ValueError(f"Judge JSON missing metric '{key}': {data}")

            norm = _normalize_1_to_5(raw_score)
            metrics[key] = MetricResult(
                name=key,
                score=norm,
                passed=norm >= self.PASS_THRESHOLD,
                details={
                    "mode": "live",
                    "raw_score": raw_score,
                    "rationale": rationale,
                    "judge_model": self.last_judge_telemetry.get("judge_model", self.model),
                },
            )
        return metrics

    def _evaluate_live(
        self,
        case: EvalCase,
        reply: str,
        retrieved_chunks: list[dict[str, Any]],
    ) -> dict[str, MetricResult]:
        if not self.gemini_api_key and not self.openai_api_key:
            raise RuntimeError("LLM API key not configured for LLMJudgeEvaluator(mode='live')")

        prompt = self._build_judge_prompt(case, reply, retrieved_chunks)
        t0 = time.perf_counter()
        last_error: Exception | None = None

        if self.gemini_api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.gemini_api_key)
                candidate_models = [
                    self.model,
                    "gemini-3.5-flash-lite",
                    "gemini-3.1-flash-lite",
                    "gemini-3.5-flash",
                    "gemini-2.5-flash",
                ]
                seen: set[str] = set()
                models = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

                for m in models:
                    try:
                        res = client.models.generate_content(
                            model=m,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=_JUDGE_SYSTEM_PROMPT,
                                response_mime_type="application/json",
                                temperature=0.0,
                            ),
                        )
                        if res and res.text:
                            usage = extract_gemini_usage(res)
                            self.last_judge_telemetry = {
                                "judge_provider": "gemini",
                                "judge_model": m,
                                "judge_ms": round((time.perf_counter() - t0) * 1000, 2),
                                **{f"judge_{k}": v for k, v in usage.items()},
                            }
                            return self._parse_judge_json(res.text)
                    except Exception as me:
                        last_error = me
                        continue
            except Exception as e:
                last_error = e

        if self.openai_api_key:
            try:
                import openai

                client = openai.OpenAI(api_key=self.openai_api_key)
                model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
                res = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                text = res.choices[0].message.content or "{}"
                usage = extract_openai_usage(res)
                self.last_judge_telemetry = {
                    "judge_provider": "openai",
                    "judge_model": model_name,
                    "judge_ms": round((time.perf_counter() - t0) * 1000, 2),
                    **{f"judge_{k}": v for k, v in usage.items()},
                }
                return self._parse_judge_json(text)
            except Exception as e:
                last_error = e

        raise RuntimeError(f"LLMJudgeEvaluator live execution failed: {last_error}")
