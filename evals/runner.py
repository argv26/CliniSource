"""Evaluation ops runner executing benchmark datasets across retrieval-only, offline, and live modes."""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agent.orchestrator import AgentOrchestrator
from agent.planner import ClinicalPlan
from context.manager import ContextManager
from evals.evaluators import LLMJudgeEvaluator, evaluate_deterministic
from evals.reporter import (
    compare_against_baseline,
    compute_aggregate_scores,
    compute_category_scores,
    compute_ops_summary,
)
from evals.schema import (
    CaseEvalResult,
    EvalCase,
    EvalDataset,
    EvalRunReport,
    MetricResult,
    StageMetrics,
)
from retrieval.parallel import _execute_parallel_retrieval
from retrieval.router import SemanticBookRouter
from retrieval.tools import get_chunk

_CONVERSATIONAL_PATTERNS = (
    re.compile(r"^(?:hi|hello|hey|hola|greetings|howdy|good\s+(?:morning|afternoon|evening|day))[\s!.]*$"),
    re.compile(r"^(?:thanks|thank\s+you|awesome|great|cool|ok|okay)[\s!.]*$"),
    re.compile(
        r"(?:are\s+you\s+(?:using\s+)?(?:a\s+)?(?:google\s+)?(?:llm|ai|gpt|gemini|model|claude|robot|bot)|"
        r"who\s+(?:created|made|developed|built)\s+you|"
        r"what\s+(?:model|llm|ai)\s+are\s+you|"
        r"how\s+do\s+you\s+work)"
    ),
)

_PLAN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "between", "by", "can", "do", "does",
    "each", "for", "from", "how", "in", "into", "is", "it", "of", "on", "or", "that",
    "the", "their", "this", "to", "what", "when", "where", "which", "why", "with",
    # Generic clinical question phrasing (keep queries focused on medical nouns/acronyms)
    "abnormalities", "aid", "anatomical", "approach", "assessed", "biochemical",
    "boundaries", "causative", "causes", "characterize", "classified", "clinical",
    "common", "compare", "components", "confirm", "contents", "contraindicated",
    "core", "criteria", "define", "defined", "describe", "diagnosis", "diagnostic",
    "differ", "differentiate", "distinguishing", "effect", "evaluation", "exact",
    "explain", "factors", "features", "finding", "findings", "first", "first-line",
    "following", "functional", "govern", "include", "including", "indicators",
    "initial", "key", "limit", "line", "major", "management", "manifest",
    "manifestations", "options", "organisms", "organization", "pathway", "pillars",
    "pressures", "primary", "principles", "produced", "risk", "role", "screening",
    "sequence", "signs", "specific", "steps", "structural", "such", "surgical",
    "suspected", "systemic", "testing", "tests", "therapy", "used", "using",
    "versus", "vs", "workup",
}


def _is_fastpath_query(query: str) -> bool:
    q = query.strip().lower()
    return any(p.search(q) for p in _CONVERSATIONAL_PATTERNS)


class DeterministicPlanStub:
    """Zero-API-cost heuristic planner used in retrieval-only and offline eval modes."""

    def __init__(self) -> None:
        self.last_telemetry: dict[str, Any] = {}

    def plan(
        self,
        user_message: str,
        book_catalog: list[dict[str, Any]] | None = None,
        active_books: list[str] | None = None,
    ) -> ClinicalPlan:
        t0 = time.perf_counter()
        raw_words = re.findall(r"\b[a-zA-Z0-9-]{2,}\b", user_message)
        terms: list[str] = []
        seen: set[str] = set()
        for w in raw_words:
            wl = w.lower()
            if wl in _PLAN_STOPWORDS or wl in seen:
                continue
            seen.add(wl)
            terms.append(w)

        queries: list[str] = []
        candidates: list[str] = []
        if len(terms) >= 2:
            candidates.append(" ".join(terms[:2]))
            candidates.append(" ".join(terms[-2:]))
        if len(terms) >= 4:
            candidates.append(" ".join(terms[2:4]))
        elif len(terms) == 3:
            candidates.append(" ".join(terms[1:3]))

        seen_q: set[str] = set()
        for q in candidates:
            ql = q.lower()
            if ql not in seen_q:
                seen_q.add(ql)
                queries.append(q)
                if len(queries) >= 3:
                    break

        if not queries:
            clean = re.sub(r"[^\w\s-]", " ", user_message).strip()
            queries = [clean] if clean else [user_message]

        self.last_telemetry = {
            "planner_ms": round((time.perf_counter() - t0) * 1000, 2),
            "planner_provider": "stub",
            "planner_model": "deterministic-stub",
        }
        return ClinicalPlan(
            diagnostic_hypotheses=[],
            organ_systems=[],
            search_queries=queries,
            evidence_checklist=[],
        )


def _extract_retrieved_chunks(
    context_manager: ContextManager,
    session_id: str,
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collects full chunk dicts (with text) from session tool outputs and citations."""
    session = context_manager.get_or_create_session(session_id)
    chunks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for msg in session.messages:
        if msg.role != "tool":
            continue
        try:
            payload = json.loads(msg.content)
        except Exception:
            continue

        candidates: list[dict[str, Any]] = []
        if isinstance(payload, list):
            candidates = [x for x in payload if isinstance(x, dict) and "text" in x]
        elif isinstance(payload, dict) and isinstance(payload.get("chunks"), list):
            candidates = [x for x in payload["chunks"] if isinstance(x, dict) and "text" in x]

        for item in candidates:
            cid = str(item.get("chunk_id") or "")
            if cid and cid in seen_ids:
                continue
            if cid:
                seen_ids.add(cid)
            chunks.append(item)

    # Hydrate any cited chunks not already extracted from tool payloads
    for cit in citations or []:
        cid = str(cit.get("chunk_id") or "")
        if not cid or cid in seen_ids:
            continue
        try:
            hydrated = get_chunk(cid)
            if isinstance(hydrated, dict) and "text" in hydrated:
                seen_ids.add(cid)
                chunks.append(hydrated)
        except Exception:
            continue

    return chunks


class EvalRunner:
    """Executes golden benchmark cases across retrieval-only, offline, or live pipelines."""

    VALID_MODES = ("retrieval-only", "offline", "live")
    VALID_TRANSPORTS = ("stream", "sync")

    def __init__(
        self,
        mode: str = "retrieval-only",
        judge_mode: str | None = None,
        transport: str = "stream",
        router: SemanticBookRouter | None = None,
    ):
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of {self.VALID_MODES}.")
        if transport not in self.VALID_TRANSPORTS:
            raise ValueError(f"Invalid transport '{transport}'. Must be one of {self.VALID_TRANSPORTS}.")

        self.mode = mode
        if judge_mode is None:
            self.judge_mode = "none" if mode == "retrieval-only" else mode
        else:
            if judge_mode not in ("none", "offline", "live"):
                raise ValueError(f"Invalid judge_mode '{judge_mode}'. Use none, offline, or live.")
            self.judge_mode = judge_mode

        self.transport = transport
        self.router = router or SemanticBookRouter()
        self.judge = (
            LLMJudgeEvaluator(mode=self.judge_mode)
            if self.judge_mode in ("offline", "live")
            else None
        )

    def run(
        self,
        dataset: EvalDataset,
        category: str | None = None,
        case_ids: list[str] | None = None,
        limit: int | None = None,
        baseline: EvalRunReport | None = None,
        max_score_drop: float = 0.05,
        max_p95_regression_ratio: float = 0.25,
        progress_cb: Callable[[int, int, CaseEvalResult], None] | None = None,
    ) -> EvalRunReport:
        cases = dataset.filter(category=category, case_ids=case_ids, limit=limit)
        results: list[CaseEvalResult] = []
        total = len(cases)

        for idx, case in enumerate(cases, start=1):
            res = self._run_single_case(case)
            results.append(res)
            if progress_cb:
                progress_cb(idx, total, res)

        agg_scores = compute_aggregate_scores(results)
        cat_scores = compute_category_scores(results)
        ops_summary = compute_ops_summary(results)
        passed_cases = sum(1 for r in results if r.passed)

        now = datetime.now(timezone.utc)
        run_id = f"eval_{self.mode}_{now.strftime('%Y%m%d_%H%M%S')}"
        report = EvalRunReport(
            run_id=run_id,
            timestamp=now.isoformat(),
            mode=self.mode,
            judge_mode=self.judge_mode,
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            total_cases=len(results),
            passed_cases=passed_cases,
            aggregate_scores=agg_scores,
            category_scores=cat_scores,
            ops_summary=ops_summary,
            results=results,
        )

        if baseline is not None:
            report.regressions = compare_against_baseline(
                report,
                baseline,
                max_score_drop=max_score_drop,
                max_p95_regression_ratio=max_p95_regression_ratio,
            )

        return report

    def _run_single_case(self, case: EvalCase) -> CaseEvalResult:
        try:
            if self.mode == "retrieval-only":
                return self._execute_retrieval_only(case)
            return self._execute_agent_case(case)
        except Exception as exc:
            return CaseEvalResult(
                case_id=case.id,
                category=case.category,
                query=case.query,
                scores={
                    "execution": MetricResult(
                        name="execution",
                        score=0.0,
                        passed=False,
                        details={"error": str(exc)},
                    )
                },
                overall_score=0.0,
                passed=False,
                error=str(exc),
            )

    def _execute_retrieval_only(self, case: EvalCase) -> CaseEvalResult:
        t_start = time.perf_counter()
        metrics = StageMetrics(provider="retrieval-only", model_used="fts5-bm25")

        if _is_fastpath_query(case.query):
            metrics.provider = "fastpath"
            metrics.model_used = "fastpath-regex"
            metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            scores = evaluate_deterministic(
                case=case,
                routed_books=[],
                retrieved_chunks=[],
                figures=[],
                total_ms=metrics.total_ms,
                retrieval_only=True,
            )
            overall = round(sum(m.score for m in scores.values()) / max(len(scores), 1), 4)
            return CaseEvalResult(
                case_id=case.id,
                category=case.category,
                query=case.query,
                routed_books=[],
                metrics=metrics,
                scores=scores,
                overall_score=overall,
                passed=all(m.passed for m in scores.values()),
            )

        stub = DeterministicPlanStub()
        t_plan = time.perf_counter()
        plan = stub.plan(case.query, active_books=case.active_books)
        metrics.planner_ms = round((time.perf_counter() - t_plan) * 1000, 2)

        t_route = time.perf_counter()
        routed_books = self.router.route(
            query=case.query,
            plan=plan,
            user_selected_books=case.active_books,
        )
        metrics.routing_ms = round((time.perf_counter() - t_route) * 1000, 2)

        t_ret = time.perf_counter()
        retrieval = _execute_parallel_retrieval(
            query=plan.search_queries or [case.query],
            allowed_books=routed_books,
            chunk_limit=6,
            section_limit=2,
            figure_limit=4 if case.require_figures else 0,
        )
        metrics.retrieval_ms = round((time.perf_counter() - t_ret) * 1000, 2)
        metrics.total_ms = round((time.perf_counter() - t_start) * 1000, 2)

        chunks = retrieval.get("chunks", [])
        figures = retrieval.get("figures", [])

        scores = evaluate_deterministic(
            case=case,
            routed_books=routed_books,
            retrieved_chunks=chunks,
            figures=figures,
            total_ms=metrics.total_ms,
            retrieval_only=True,
        )
        overall = round(sum(m.score for m in scores.values()) / max(len(scores), 1), 4)
        return CaseEvalResult(
            case_id=case.id,
            category=case.category,
            query=case.query,
            routed_books=routed_books,
            figure_count=len(figures),
            metrics=metrics,
            scores=scores,
            overall_score=overall,
            passed=all(m.passed for m in scores.values()),
        )

    def _execute_agent_case(self, case: EvalCase) -> CaseEvalResult:
        cm = ContextManager()
        if self.mode == "offline":
            orch = AgentOrchestrator(
                context_manager=cm,
                planner=DeterministicPlanStub(),
                router=self.router,
            )
            orch.gemini_api_key = None
            orch.openai_api_key = None
        else:
            orch = AgentOrchestrator(
                context_manager=cm,
                router=self.router,
            )

        session_id = f"eval_{case.id}_{uuid.uuid4().hex[:8]}"
        reply = ""
        citations: list[dict[str, Any]] = []
        figures: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        routed_books: list[str] = []
        raw_telemetry: dict[str, Any] = {}

        if self.transport == "stream":
            for evt in orch.stream_turn(
                session_id=session_id,
                user_message=case.query,
                active_books=case.active_books,
            ):
                etype = evt.get("event")
                edata = evt.get("data")
                if etype == "tools" and isinstance(edata, list):
                    tool_calls = edata
                elif etype == "citations" and isinstance(edata, list):
                    citations = edata
                elif etype == "figures" and isinstance(edata, list):
                    figures = edata
                elif etype == "done" and isinstance(edata, dict):
                    reply = str(edata.get("reply") or "")
                    routed_books = list(edata.get("routed_books") or [])
                    raw_telemetry = dict(edata.get("telemetry") or {})
        else:
            res = orch.run_turn(
                session_id=session_id,
                user_message=case.query,
                active_books=case.active_books,
            )
            reply = str(res.get("reply") or "")
            citations = list(res.get("citations") or [])
            figures = list(res.get("figures") or [])
            tool_calls = list(res.get("tool_calls") or [])
            routed_books = list(res.get("routed_books") or [])
            raw_telemetry = dict(res.get("telemetry") or {})

        metrics = StageMetrics.from_dict(raw_telemetry)
        retrieved_chunks = _extract_retrieved_chunks(cm, session_id, citations)

        scores = evaluate_deterministic(
            case=case,
            routed_books=routed_books,
            retrieved_chunks=retrieved_chunks,
            reply=reply,
            citations=citations,
            tool_calls=tool_calls,
            figures=figures,
            total_ms=metrics.total_ms,
            retrieval_only=False,
        )

        if self.judge is not None:
            judge_scores = self.judge.evaluate(case, reply, retrieved_chunks)
            scores.update(judge_scores)

        overall = round(sum(m.score for m in scores.values()) / max(len(scores), 1), 4)
        return CaseEvalResult(
            case_id=case.id,
            category=case.category,
            query=case.query,
            routed_books=routed_books,
            reply=reply,
            citation_count=len(citations),
            figure_count=len(figures),
            tool_calls=tool_calls,
            metrics=metrics,
            scores=scores,
            overall_score=overall,
            passed=all(m.passed for m in scores.values()),
        )
