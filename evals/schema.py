"""Core schemas and JSON serialization for the LLM Eval Ops test suite."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


VALID_CATEGORIES = {
    "clinical_factual",
    "differential_diagnosis",
    "table_criteria",
    "anatomy_figure",
    "multi_book",
    "conversational_fastpath",
    "out_of_scope",
}


@dataclass
class EvalCase:
    """Single golden benchmark evaluation case."""

    id: str
    category: str
    query: str
    active_books: list[str] | None = None
    expected_books: list[str] = field(default_factory=list)
    expected_keywords_in_chunks: list[str] = field(default_factory=list)
    expected_answer_points: list[str] = field(default_factory=list)
    require_citations: bool = True
    require_table: bool = False
    require_figures: bool = False
    is_conversational: bool = False
    is_out_of_scope: bool = False
    max_latency_ms: float = 15000.0
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("EvalCase.id must be non-empty")
        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid EvalCase.category '{self.category}'. Must be one of {sorted(VALID_CATEGORIES)}"
            )
        if not self.query or not self.query.strip():
            raise ValueError(f"EvalCase '{self.id}' query must be non-empty")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalCase:
        return cls(
            id=str(data["id"]),
            category=str(data["category"]),
            query=str(data["query"]),
            active_books=list(data["active_books"]) if data.get("active_books") is not None else None,
            expected_books=list(data.get("expected_books") or []),
            expected_keywords_in_chunks=list(data.get("expected_keywords_in_chunks") or []),
            expected_answer_points=list(data.get("expected_answer_points") or []),
            require_citations=bool(data.get("require_citations", True)),
            require_table=bool(data.get("require_table", False)),
            require_figures=bool(data.get("require_figures", False)),
            is_conversational=bool(data.get("is_conversational", False)),
            is_out_of_scope=bool(data.get("is_out_of_scope", False)),
            max_latency_ms=float(data.get("max_latency_ms", 15000.0)),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvalDataset:
    """Collection of golden evaluation cases with metadata and filtering."""

    name: str
    version: str
    description: str = ""
    cases: list[EvalCase] = field(default_factory=list)

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for c in self.cases:
            if c.id in seen:
                raise ValueError(f"Duplicate EvalCase id detected: '{c.id}'")
            seen.add(c.id)

    @classmethod
    def load(cls, path: str | Path) -> EvalDataset:
        p = Path(path)
        raw = json.loads(p.read_text(encoding="utf-8"))
        cases = [EvalCase.from_dict(item) for item in raw.get("cases", [])]
        return cls(
            name=str(raw.get("name", p.stem)),
            version=str(raw.get("version", "1.0.0")),
            description=str(raw.get("description", "")),
            cases=cases,
        )

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "cases": [c.to_dict() for c in self.cases],
        }
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return p

    def filter(
        self,
        category: str | None = None,
        case_ids: list[str] | None = None,
        limit: int | None = None,
    ) -> list[EvalCase]:
        filtered = list(self.cases)
        if category:
            filtered = [c for c in filtered if c.category == category]
        if case_ids:
            id_set = set(case_ids)
            filtered = [c for c in filtered if c.id in id_set]
        if limit is not None and limit >= 0:
            filtered = filtered[:limit]
        return filtered


@dataclass
class StageMetrics:
    """Operational telemetry captured for a single evaluation turn."""

    planner_ms: float = 0.0
    routing_ms: float = 0.0
    retrieval_ms: float = 0.0
    ttft_ms: float = 0.0
    llm_ms: float = 0.0
    total_ms: float = 0.0
    provider: str = ""
    model_used: str = ""
    fallback_triggered: bool = False
    fallback_reason: str = ""
    react_iterations: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageMetrics:
        return cls(
            planner_ms=float(data.get("planner_ms", 0.0)),
            routing_ms=float(data.get("routing_ms", 0.0)),
            retrieval_ms=float(data.get("retrieval_ms", 0.0)),
            ttft_ms=float(data.get("ttft_ms", 0.0)),
            llm_ms=float(data.get("llm_ms", 0.0)),
            total_ms=float(data.get("total_ms", 0.0)),
            provider=str(data.get("provider", "")),
            model_used=str(data.get("model_used", "")),
            fallback_triggered=bool(data.get("fallback_triggered", False)),
            fallback_reason=str(data.get("fallback_reason", "")),
            react_iterations=int(data.get("react_iterations", 0)),
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            cached_tokens=int(data.get("cached_tokens", 0)),
            completion_tokens=int(data.get("completion_tokens", 0)),
            total_tokens=int(data.get("total_tokens", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricResult:
    """Result of an individual evaluator check for one test case."""

    name: str
    score: float
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.score = max(0.0, min(1.0, float(self.score)))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricResult:
        return cls(
            name=str(data["name"]),
            score=float(data["score"]),
            passed=bool(data["passed"]),
            details=dict(data.get("details") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseEvalResult:
    """Complete evaluation outcome for one EvalCase."""

    case_id: str
    category: str
    query: str
    routed_books: list[str] = field(default_factory=list)
    reply: str = ""
    citation_count: int = 0
    figure_count: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metrics: StageMetrics = field(default_factory=StageMetrics)
    scores: dict[str, MetricResult] = field(default_factory=dict)
    overall_score: float = 0.0
    passed: bool = True
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaseEvalResult:
        raw_scores = data.get("scores") or {}
        scores = {k: MetricResult.from_dict(v) for k, v in raw_scores.items()}
        return cls(
            case_id=str(data["case_id"]),
            category=str(data["category"]),
            query=str(data["query"]),
            routed_books=list(data.get("routed_books") or []),
            reply=str(data.get("reply") or ""),
            citation_count=int(data.get("citation_count", 0)),
            figure_count=int(data.get("figure_count", 0)),
            tool_calls=list(data.get("tool_calls") or []),
            metrics=StageMetrics.from_dict(data.get("metrics") or {}),
            scores=scores,
            overall_score=float(data.get("overall_score", 0.0)),
            passed=bool(data.get("passed", False)),
            error=data.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "query": self.query,
            "routed_books": self.routed_books,
            "reply": self.reply,
            "citation_count": self.citation_count,
            "figure_count": self.figure_count,
            "tool_calls": self.tool_calls,
            "metrics": self.metrics.to_dict(),
            "scores": {k: v.to_dict() for k, v in self.scores.items()},
            "overall_score": self.overall_score,
            "passed": self.passed,
            "error": self.error,
        }


@dataclass
class EvalRunReport:
    """Aggregate report across all evaluated cases for an ops run."""

    run_id: str
    timestamp: str
    mode: str
    judge_mode: str
    dataset_name: str
    dataset_version: str
    total_cases: int
    passed_cases: int
    aggregate_scores: dict[str, float] = field(default_factory=dict)
    category_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    ops_summary: dict[str, Any] = field(default_factory=dict)
    regressions: list[str] = field(default_factory=list)
    results: list[CaseEvalResult] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> EvalRunReport:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            run_id=str(raw["run_id"]),
            timestamp=str(raw["timestamp"]),
            mode=str(raw["mode"]),
            judge_mode=str(raw.get("judge_mode", "none")),
            dataset_name=str(raw["dataset_name"]),
            dataset_version=str(raw["dataset_version"]),
            total_cases=int(raw["total_cases"]),
            passed_cases=int(raw["passed_cases"]),
            aggregate_scores=dict(raw.get("aggregate_scores") or {}),
            category_scores=dict(raw.get("category_scores") or {}),
            ops_summary=dict(raw.get("ops_summary") or {}),
            regressions=list(raw.get("regressions") or []),
            results=[CaseEvalResult.from_dict(r) for r in raw.get("results", [])],
        )

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "mode": self.mode,
            "judge_mode": self.judge_mode,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "aggregate_scores": self.aggregate_scores,
            "category_scores": self.category_scores,
            "ops_summary": self.ops_summary,
            "regressions": self.regressions,
            "results": [r.to_dict() for r in self.results],
        }
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return p
