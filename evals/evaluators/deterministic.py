"""Deterministic zero-API-cost evaluators for routing, retrieval, citations, format, and SLAs."""
from __future__ import annotations

import re
from typing import Any

from evals.schema import EvalCase, MetricResult


_MERMAID_RE = re.compile(r"```mermaid\b", re.IGNORECASE)
_STRAY_DOLLAR_RE = re.compile(r"\d+\$(?!\d)")
_RAW_LATEX_TEXT_RE = re.compile(r"\\text\{")
_CITATION_PILL_RE = re.compile(r"\[(\d+)\]")
_MD_TABLE_RE = re.compile(r"^\|.+\|\s*\n\|[\s:\-\|]+\|", re.MULTILINE)
_FILLER_OPENING_RE = re.compile(
    r"^(?:sure[!,\.]?|certainly[!,\.]?|of course[!,\.]?|as an ai\b|i would be happy to\b|here is\b)",
    re.IGNORECASE,
)
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


def score_routing(case: EvalCase, routed_books: list[str]) -> MetricResult:
    """Evaluates SemanticBookRouter accuracy and User Selection Sovereignty."""
    routed = list(routed_books or [])

    if case.is_conversational:
        passed = len(routed) == 0
        return MetricResult(
            name="routing",
            score=1.0 if passed else 0.0,
            passed=passed,
            details={"routed_books": routed, "expected_books": [], "note": "conversational_fastpath"},
        )

    if case.is_out_of_scope and not case.expected_books:
        return MetricResult(
            name="routing",
            score=1.0,
            passed=True,
            details={"routed_books": routed, "expected_books": [], "note": "out_of_scope_na"},
        )

    if case.active_books is not None and len(case.active_books) > 0:
        expected_set = set(case.active_books)
        routed_set = set(routed)
        sovereignty_ok = routed_set == expected_set
        return MetricResult(
            name="routing",
            score=1.0 if sovereignty_ok else 0.0,
            passed=sovereignty_ok,
            details={
                "sovereignty_mode": True,
                "active_books": list(case.active_books),
                "routed_books": routed,
                "sovereignty_preserved": sovereignty_ok,
            },
        )

    expected_set = set(case.expected_books)
    if not expected_set:
        return MetricResult(
            name="routing",
            score=1.0,
            passed=True,
            details={"routed_books": routed, "expected_books": []},
        )

    routed_set = set(routed)
    overlap = expected_set & routed_set
    recall = len(overlap) / len(expected_set)
    top1_match = bool(routed and routed[0] in expected_set)

    # Single expected book requires exact inclusion; multi-book expected passes if >=1 primary book routed
    passed = (recall == 1.0) if len(expected_set) == 1 else (len(overlap) >= 1)
    return MetricResult(
        name="routing",
        score=recall,
        passed=passed,
        details={
            "sovereignty_mode": False,
            "expected_books": list(case.expected_books),
            "routed_books": routed,
            "matched_books": sorted(overlap),
            "top1_match": top1_match,
        },
    )


def score_retrieval(
    case: EvalCase,
    retrieved_chunks: list[dict[str, Any]],
    k: int = 6,
) -> dict[str, MetricResult]:
    """Computes Hit@K, MRR, and keyword coverage across top-K retrieved chunks."""
    chunks = list(retrieved_chunks or [])

    if case.is_conversational:
        passed = len(chunks) == 0
        val = 1.0 if passed else 0.0
        note = {"note": "conversational_fastpath", "chunk_count": len(chunks)}
        return {
            "retrieval_hit_at_k": MetricResult("retrieval_hit_at_k", val, passed, note),
            "retrieval_mrr": MetricResult("retrieval_mrr", val, passed, note),
            "retrieval_keyword_coverage": MetricResult("retrieval_keyword_coverage", val, passed, note),
        }

    if case.is_out_of_scope or not case.expected_keywords_in_chunks:
        note = {"note": "na_for_case", "chunk_count": len(chunks)}
        return {
            "retrieval_hit_at_k": MetricResult("retrieval_hit_at_k", 1.0, True, note),
            "retrieval_mrr": MetricResult("retrieval_mrr", 1.0, True, note),
            "retrieval_keyword_coverage": MetricResult("retrieval_keyword_coverage", 1.0, True, note),
        }

    top_chunks = chunks[:k]
    expected_kws = [kw.lower() for kw in case.expected_keywords_in_chunks if kw.strip()]
    expected_books = set(case.expected_books) if case.expected_books else set()
    min_kw_for_relevant_chunk = max(1, (len(expected_kws) + 1) // 2)

    first_relevant_rank: int | None = None
    matched_kws_union: set[str] = set()
    ref_chunks_count = 0

    for rank, chunk in enumerate(top_chunks, start=1):
        heading = str(chunk.get("heading_path") or "")
        text = str(chunk.get("text") or "")
        if heading.strip().lower().endswith("references"):
            ref_chunks_count += 1

        haystack = f"{heading} {text}".lower()
        chunk_matched = {kw for kw in expected_kws if kw in haystack}
        matched_kws_union.update(chunk_matched)

        chunk_book = chunk.get("book_slug")
        book_ok = (not expected_books) or (not chunk_book) or (chunk_book in expected_books)

        if book_ok and len(chunk_matched) >= min_kw_for_relevant_chunk and first_relevant_rank is None:
            first_relevant_rank = rank

    hit_score = 1.0 if first_relevant_rank is not None else 0.0
    mrr_score = (1.0 / first_relevant_rank) if first_relevant_rank is not None else 0.0
    coverage_score = (len(matched_kws_union) / len(expected_kws)) if expected_kws else 1.0

    details = {
        "k": k,
        "retrieved_count": len(top_chunks),
        "first_relevant_rank": first_relevant_rank,
        "matched_keywords": sorted(matched_kws_union),
        "missing_keywords": sorted(set(expected_kws) - matched_kws_union),
        "references_chunks_in_top_k": ref_chunks_count,
    }

    return {
        "retrieval_hit_at_k": MetricResult(
            name="retrieval_hit_at_k",
            score=hit_score,
            passed=hit_score == 1.0,
            details=details,
        ),
        "retrieval_mrr": MetricResult(
            name="retrieval_mrr",
            score=mrr_score,
            passed=mrr_score > 0.0,
            details=details,
        ),
        "retrieval_keyword_coverage": MetricResult(
            name="retrieval_keyword_coverage",
            score=coverage_score,
            passed=coverage_score >= 0.66,
            details=details,
        ),
    }


def score_citation_integrity(
    case: EvalCase,
    reply: str,
    citations: list[dict[str, Any]],
) -> MetricResult:
    """Validates 1-based [N] citations map to verified records with zero phantom pills."""
    text = reply or ""
    cit_list = list(citations or [])
    valid_ids = {int(c["citation_id"]) for c in cit_list if "citation_id" in c}
    used_ids = {int(m) for m in _CITATION_PILL_RE.findall(text)}
    phantom_ids = sorted(used_ids - valid_ids)

    if case.is_conversational:
        passed = len(used_ids) == 0 and len(cit_list) == 0
        return MetricResult(
            name="citation_integrity",
            score=1.0 if passed else 0.0,
            passed=passed,
            details={"used_ids": sorted(used_ids), "valid_ids": sorted(valid_ids), "phantom_ids": phantom_ids},
        )

    score = 1.0
    issues: list[str] = []

    if phantom_ids:
        score -= 0.5
        issues.append(f"Phantom citation IDs emitted: {phantom_ids}")

    if case.require_citations:
        if not valid_ids:
            score -= 0.5
            issues.append("No citation records registered for clinical query")
        elif not (used_ids & valid_ids):
            score -= 0.5
            issues.append("Reply contains zero valid inline [N] citation pills")

    score = max(0.0, score)
    passed = len(phantom_ids) == 0 and (
        not case.require_citations or (len(valid_ids) > 0 and len(used_ids & valid_ids) > 0)
    )
    return MetricResult(
        name="citation_integrity",
        score=score,
        passed=passed,
        details={
            "used_ids": sorted(used_ids),
            "valid_ids": sorted(valid_ids),
            "phantom_ids": phantom_ids,
            "issues": issues,
        },
    )


def score_format_compliance(case: EvalCase, reply: str) -> MetricResult:
    """Checks Zero Synthetic Flowcharts, typography hygiene, direct answer first, and table compliance."""
    text = (reply or "").strip()
    if not text:
        return MetricResult(
            name="format_compliance",
            score=0.0,
            passed=False,
            details={"issues": ["Empty reply"]},
        )

    no_mermaid = not bool(_MERMAID_RE.search(text))
    no_stray_dollar = not bool(_STRAY_DOLLAR_RE.search(text))
    no_raw_latex = not bool(_RAW_LATEX_TEXT_RE.search(text))
    table_present = bool(_MD_TABLE_RE.search(text))

    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    direct_answer_first = (
        len(first_line) >= 15
        and not first_line.startswith("#")
        and not bool(_FILLER_OPENING_RE.match(first_line))
    )

    # Strip fenced code blocks before checking bold balance
    non_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    balanced_bold = (non_code.count("**") % 2) == 0

    checks: list[bool] = [no_mermaid, no_stray_dollar, no_raw_latex, direct_answer_first, balanced_bold]
    if case.require_table:
        checks.append(table_present)

    score = sum(1.0 for c in checks if c) / len(checks)

    issues: list[str] = []
    if not no_mermaid:
        issues.append("Contains forbidden synthetic mermaid block")
    if not no_stray_dollar:
        issues.append("Contains stray trailing dollar sign (e.g. 15$)")
    if not no_raw_latex:
        issues.append("Contains raw LaTeX \\text{...} artifact")
    if not direct_answer_first:
        issues.append("Opening line uses conversational filler or is too short")
    if not balanced_bold:
        issues.append("Unbalanced Markdown ** bold markers")
    if case.require_table and not table_present:
        issues.append("Required Markdown table missing")

    # Hard gates: no mermaid, no stray dollar, and required table when mandated
    passed = no_mermaid and no_stray_dollar and no_raw_latex and (not case.require_table or table_present)
    if not no_mermaid:
        score = 0.0

    return MetricResult(
        name="format_compliance",
        score=score,
        passed=passed,
        details={
            "no_mermaid": no_mermaid,
            "no_stray_dollar": no_stray_dollar,
            "no_raw_latex": no_raw_latex,
            "direct_answer_first": direct_answer_first,
            "balanced_bold": balanced_bold,
            "table_present": table_present,
            "table_required": case.require_table,
            "issues": issues,
        },
    )


def score_fastpath_and_scope(
    case: EvalCase,
    reply: str,
    tool_calls: list[dict[str, Any]],
) -> MetricResult:
    """Checks fast-path zero-tool rule on greetings and honest disclosure on out-of-scope queries."""
    text = (reply or "").strip()
    tools = list(tool_calls or [])

    if case.is_conversational:
        zero_tools = len(tools) == 0
        has_reply = len(text) > 0
        passed = zero_tools and has_reply
        return MetricResult(
            name="fastpath_scope",
            score=1.0 if passed else 0.0,
            passed=passed,
            details={"tool_calls_count": len(tools), "has_reply": has_reply, "mode": "conversational"},
        )

    if case.is_out_of_scope:
        lower = text.lower()
        disclosed = any(p in lower for p in _OOS_HONESTY_PHRASES)
        return MetricResult(
            name="fastpath_scope",
            score=1.0 if disclosed else 0.0,
            passed=disclosed,
            details={"out_of_scope_disclosed": disclosed, "mode": "out_of_scope"},
        )

    substantial = len(text) >= 80
    return MetricResult(
        name="fastpath_scope",
        score=1.0 if substantial else 0.0,
        passed=substantial,
        details={"reply_length": len(text), "tool_calls_count": len(tools), "mode": "clinical"},
    )


def score_figures(case: EvalCase, figures: list[dict[str, Any]] | None) -> MetricResult:
    """Checks whether visual figure evidence was surfaced when required by the case."""
    figs = list(figures or [])
    if not case.require_figures:
        return MetricResult(
            name="figure_presence",
            score=1.0,
            passed=True,
            details={"figure_count": len(figs), "required": False},
        )
    passed = len(figs) > 0
    return MetricResult(
        name="figure_presence",
        score=1.0 if passed else 0.0,
        passed=passed,
        details={"figure_count": len(figs), "required": True},
    )


def score_latency_sla(case: EvalCase, total_ms: float) -> MetricResult:
    """Checks whether turn execution stayed within the EvalCase max_latency_ms budget."""
    budget = float(case.max_latency_ms)
    if total_ms <= 0:
        return MetricResult(
            name="latency_sla",
            score=1.0,
            passed=True,
            details={"total_ms": total_ms, "max_latency_ms": budget, "note": "timing_not_recorded"},
        )

    passed = total_ms <= budget
    if passed:
        score = 1.0
    else:
        # Smooth decay beyond budget up to 2x budget -> 0.0
        over_ratio = (total_ms - budget) / max(budget, 1.0)
        score = max(0.0, 1.0 - over_ratio)

    return MetricResult(
        name="latency_sla",
        score=score,
        passed=passed,
        details={"total_ms": round(total_ms, 2), "max_latency_ms": budget},
    )


def evaluate_deterministic(
    case: EvalCase,
    routed_books: list[str],
    retrieved_chunks: list[dict[str, Any]],
    reply: str = "",
    citations: list[dict[str, Any]] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    figures: list[dict[str, Any]] | None = None,
    total_ms: float = 0.0,
    retrieval_only: bool = False,
) -> dict[str, MetricResult]:
    """Runs all applicable deterministic evaluators for a single case."""
    results: dict[str, MetricResult] = {}
    results["routing"] = score_routing(case, routed_books)
    results.update(score_retrieval(case, retrieved_chunks))

    if case.require_figures:
        results["figure_presence"] = score_figures(case, figures)

    if not retrieval_only:
        results["citation_integrity"] = score_citation_integrity(case, reply, citations or [])
        results["format_compliance"] = score_format_compliance(case, reply)
        results["fastpath_scope"] = score_fastpath_and_scope(case, reply, tool_calls or [])

    results["latency_sla"] = score_latency_sla(case, total_ms)
    return results
