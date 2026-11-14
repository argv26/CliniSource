"""Unit tests for CliniSource LLM Eval Ops schemas, evaluators, telemetry, and reporter."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.telemetry import TurnTelemetry, extract_gemini_usage, extract_openai_usage
from evals.evaluators import (
    LLMJudgeEvaluator,
    evaluate_deterministic,
    score_citation_integrity,
    score_fastpath_and_scope,
    score_figures,
    score_format_compliance,
    score_latency_sla,
    score_retrieval,
    score_routing,
)
from evals.reporter import (
    compare_against_baseline,
    compute_aggregate_scores,
    compute_category_scores,
    compute_ops_summary,
    percentile,
    render_markdown_report,
    save_report_artifacts,
)
from evals.runner import DeterministicPlanStub
from evals.schema import (
    CaseEvalResult,
    EvalCase,
    EvalDataset,
    EvalRunReport,
    MetricResult,
    StageMetrics,
)


def _sample_case(**overrides) -> EvalCase:
    payload = {
        "id": "unit-001",
        "category": "clinical_factual",
        "query": "What is the initial biochemical diagnostic workup for pheochromocytoma?",
        "active_books": None,
        "expected_books": ["Williams_Textbook_of_Endocrinology_15th_edition_2"],
        "expected_keywords_in_chunks": ["pheochromocytoma", "metanephrines", "catecholamines"],
        "expected_answer_points": [
            "Plasma free metanephrines or 24-hour urinary fractionated metanephrines",
            "Imaging localization follows biochemical confirmation",
        ],
        "require_citations": True,
        "require_table": False,
        "require_figures": False,
        "is_conversational": False,
        "is_out_of_scope": False,
        "max_latency_ms": 15000.0,
    }
    payload.update(overrides)
    return EvalCase(**payload)


def test_schema_validation_and_roundtrip(tmp_path: Path):
    # AC: EvalCase/EvalDataset validate categories and unique IDs, clamp scores, and round-trip JSON cleanly.
    # Behavior: Construct valid/invalid schemas and serialize/deserialize -> Validation raises ValueError; valid objects round-trip identically.
    # @lane: unit
    # @dependency: none
    # Selection evidence: Pure dataclass/JSON contract validation without DB or network calls.
    with pytest.raises(ValueError, match="Invalid EvalCase.category"):
        _sample_case(category="unknown_bucket")

    c1 = _sample_case(id="dup-1")
    c2 = _sample_case(id="dup-1")
    with pytest.raises(ValueError, match="Duplicate EvalCase id"):
        EvalDataset(name="bad", version="1.0", cases=[c1, c2])

    clamped_hi = MetricResult("m", 1.8, True)
    clamped_lo = MetricResult("m", -0.4, False)
    assert clamped_hi.score == 1.0
    assert clamped_lo.score == 0.0

    ds = EvalDataset(name="unit_ds", version="1.0.0", cases=[_sample_case(id="c1"), _sample_case(id="c2", category="table_criteria")])
    ds_path = tmp_path / "dataset.json"
    ds.save(ds_path)
    loaded_ds = EvalDataset.load(ds_path)
    assert len(loaded_ds.cases) == 2
    assert len(loaded_ds.filter(category="table_criteria")) == 1
    assert len(loaded_ds.filter(limit=1)) == 1

    gold_path = Path("evals/datasets/clinical_gold.json")
    gold = EvalDataset.load(gold_path)
    assert len(gold.cases) >= 20
    assert {"conversational_fastpath", "out_of_scope", "multi_book"}.issubset({c.category for c in gold.cases})


def test_score_routing_and_user_selection_sovereignty():
    # AC: score_routing validates SemanticBookRouter matching and strict User Selection Sovereignty.
    # Behavior: Evaluate active_books enforcement, single-book match, and conversational zero-book check -> Sovereignty violations fail strictly.
    # @lane: unit
    # @dependency: none
    # Selection evidence: Isolates routing logic against explicit EvalCase expectations.
    sov_case = _sample_case(active_books=["Harrison_2025_22nd_Edition"])
    assert score_routing(sov_case, ["Harrison_2025_22nd_Edition"]).score == 1.0
    assert score_routing(sov_case, ["Harrison_2025_22nd_Edition", "Williams_Textbook_of_Endocrinology_15th_edition_2"]).passed is False

    conv_case = _sample_case(category="conversational_fastpath", is_conversational=True, expected_books=[])
    assert score_routing(conv_case, []).passed is True
    assert score_routing(conv_case, ["Harrison_2025_22nd_Edition"]).score == 0.0


def test_score_retrieval_hit_mrr_and_coverage():
    # AC: score_retrieval accurately computes Hit@K, MRR, keyword coverage, and References noise count.
    # Behavior: Feed synthetic chunks where relevant passage sits at rank 2 below a References chunk -> MRR=0.5, Hit@K=1.0, ref count=1.
    # @lane: unit
    # @dependency: none
    # Selection evidence: Deterministic verification of rank-sensitive IR metrics.
    case = _sample_case()
    chunks = [
        {"book_slug": "Williams_Textbook_of_Endocrinology_15th_edition_2", "heading_path": "Ch 14 > References", "text": "Bibliography entries"},
        {"book_slug": "Williams_Textbook_of_Endocrinology_15th_edition_2", "heading_path": "Ch 14 > Case Detection", "text": "Pheochromocytoma screening uses plasma free metanephrines and catecholamines."},
    ]
    res = score_retrieval(case, chunks, k=6)
    assert res["retrieval_hit_at_k"].score == 1.0
    assert res["retrieval_mrr"].score == 0.5
    assert res["retrieval_keyword_coverage"].score == 1.0
    assert res["retrieval_hit_at_k"].details["references_chunks_in_top_k"] == 1

    miss = score_retrieval(case, [{"book_slug": "CORNEA_FundamentalsDiagnosis_and_Management_5th_Ed", "heading_path": "Cornea", "text": "Unrelated tissue"}])
    assert miss["retrieval_hit_at_k"].score == 0.0
    assert miss["retrieval_mrr"].score == 0.0


def test_score_citation_and_format_corruption_gates():
    # AC: Corrupted replies (mermaid blocks, phantom [99], trailing 15$, raw \text{}) strictly fail checks.
    # Behavior: Evaluate clean table reply vs corrupted variants -> Clean scores 1.0; mermaid scores 0.0; phantom [99] and 15$ fail.
    # @lane: unit
    # @dependency: none
    # Selection evidence: Covers every deterministic anti-pattern rule in score_citation_integrity & score_format_compliance.
    case = _sample_case(require_table=True, require_citations=True)
    citations = [{"citation_id": 1}, {"citation_id": 2}]

    clean_reply = (
        "Initial diagnosis relies on plasma free or urinary fractionated metanephrines [1].\n\n"
        "| Test | Marker |\n| :--- | :--- |\n| Screening | Plasma free metanephrines [2] |\n"
    )
    assert score_citation_integrity(case, clean_reply, citations).score == 1.0
    assert score_format_compliance(case, clean_reply).score == 1.0

    phantom = score_citation_integrity(case, "Measured metanephrines [1] and [99].", citations)
    assert phantom.passed is False
    assert phantom.details["phantom_ids"] == [99]

    no_pills = score_citation_integrity(case, "Measured metanephrines cleanly.", citations)
    assert no_pills.passed is False

    mermaid_reply = "Initial screening uses metanephrines [1].\n\n```mermaid\ngraph TD; A-->B;\n```\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    m_res = score_format_compliance(case, mermaid_reply)
    assert m_res.score == 0.0
    assert m_res.passed is False

    stray_dollar = "Threshold exceeds 15$ on repeat measurement [1].\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    assert score_format_compliance(case, stray_dollar).passed is False

    raw_latex = r"Dose in \text{mg/day} is adjusted [1]." + "\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    assert score_format_compliance(case, raw_latex).passed is False

    missing_table = "Initial screening uses plasma free metanephrines [1] before imaging."
    assert score_format_compliance(case, missing_table).passed is False

    filler = "Sure, here is the workup for pheochromocytoma [1].\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    assert score_format_compliance(case, filler).details["direct_answer_first"] is False


def test_fastpath_figures_latency_and_aggregate_eval():
    # AC: Fast-path, out-of-scope, figure presence, and SLA evaluators produce deterministic boundary scores.
    # Behavior: Test conversational zero-tools, OOS disclosure, missing required figure, and 1.5x SLA overrun -> Expected pass/decay values.
    # @lane: unit
    # @dependency: none
    # Selection evidence: Verifies secondary deterministic gates and evaluate_deterministic() wrapper.
    conv_case = _sample_case(category="conversational_fastpath", is_conversational=True, expected_books=[], require_citations=False)
    assert score_fastpath_and_scope(conv_case, "Hello! Ask a clinical question.", []).passed is True
    assert score_fastpath_and_scope(conv_case, "Hello!", [{"name": "search_chunks"}]).passed is False

    oos_case = _sample_case(category="out_of_scope", is_out_of_scope=True, expected_books=[], expected_keywords_in_chunks=[], require_citations=False)
    assert score_fastpath_and_scope(oos_case, "This topic is not covered in the indexed textbooks.", []).passed is True
    assert score_fastpath_and_scope(oos_case, "Section 179 allows $1,250,000 deduction.", []).passed is False

    fig_case = _sample_case(require_figures=True)
    assert score_figures(fig_case, []).score == 0.0
    assert score_figures(fig_case, [{"figure_id": "fig1"}]).score == 1.0

    sla = score_latency_sla(_sample_case(max_latency_ms=1000.0), 1500.0)
    assert sla.passed is False
    assert sla.score == pytest.approx(0.5)

    combined = evaluate_deterministic(
        case=fig_case,
        routed_books=["Williams_Textbook_of_Endocrinology_15th_edition_2"],
        retrieved_chunks=[{"book_slug": "Williams_Textbook_of_Endocrinology_15th_edition_2", "text": "pheochromocytoma metanephrines catecholamines"}],
        reply=(
            "Initial biochemical screening for suspected pheochromocytoma uses plasma free metanephrines "
            "or 24-hour urinary fractionated metanephrines [1]."
        ),
        citations=[{"citation_id": 1}],
        tool_calls=[{"name": "search_chunks"}],
        figures=[{"figure_id": "fig1"}],
        total_ms=250.0,
        retrieval_only=False,
    )
    assert all(v.passed for v in combined.values()), {k: v.details for k, v in combined.items() if not v.passed}


def test_llm_judge_offline_and_mocked_live():
    # AC: LLMJudgeEvaluator supports zero-API offline heuristic and structured fenced-JSON live scoring.
    # Behavior: Evaluate supported vs hallucinated reply in offline mode, plus mocked Gemini JSON response -> Supported > Hallucinated cleanly.
    # @lane: unit
    # @dependency: none
    # Selection evidence: Verifies semantic rubric behavior without spending live API quota.
    case = _sample_case()
    chunks = [
        {
            "book_slug": "Williams_Textbook_of_Endocrinology_15th_edition_2",
            "page_start": 683,
            "heading_path": "Pheochromocytoma",
            "text": "Suspected pheochromocytoma is tested initially with plasma free metanephrines or 24-hour urinary fractionated metanephrines followed by CT or MRI localization.",
        }
    ]
    off = LLMJudgeEvaluator(mode="offline")
    supported = (
        "Initial testing uses plasma free metanephrines or 24-hour urinary fractionated metanephrines [1], "
        "followed by imaging localization with CT or MRI [1]."
    )
    hallucinated = "Diagnose exclusively with 72-hour fasting insulin over 450 mg/dL and treat with 950 mg prednisolone [1]."

    good = off.evaluate(case, supported, chunks)
    bad = off.evaluate(case, hallucinated, chunks)
    assert good["faithfulness"].score >= 0.75 and good["faithfulness"].passed
    assert good["answer_completeness"].score >= 0.75
    assert bad["faithfulness"].score < good["faithfulness"].score
    assert not bad["faithfulness"].passed

    live = LLMJudgeEvaluator(mode="live", gemini_api_key="dummy-key")
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = """```json
    {
      "faithfulness": {"score": 5, "rationale": "Grounded in cited passage."},
      "answer_completeness": {"score": 4, "rationale": "Covers testing and imaging."},
      "clinical_soundness": {"score": 5, "rationale": "Clinically safe."}
    }
    ```"""
    mock_res.usage_metadata = None
    mock_client.models.generate_content.return_value = mock_res
    with patch("google.genai.Client", return_value=mock_client):
        res = live.evaluate(case, supported, chunks)
    assert res["faithfulness"].score == 1.0
    assert res["answer_completeness"].score == 0.75
    assert live.last_judge_telemetry["judge_provider"] == "gemini"


def test_telemetry_extraction_plan_stub_and_reporter(tmp_path: Path):
    # AC: Telemetry extractors handle MagicMock safely; reporter computes percentiles, detects regressions, and renders MD/JSON.
    # Behavior: Extract mock & int usage, run DeterministicPlanStub, compare degraded report vs baseline -> Exact regression flags and files created.
    # @lane: unit
    # @dependency: none
    # Selection evidence: Covers telemetry safety, query stubbing, and ops reporting end-to-end without DB/network.
    assert extract_gemini_usage(MagicMock())["total_tokens"] == 0
    assert extract_openai_usage(MagicMock())["total_tokens"] == 0

    real_usage = MagicMock()
    real_usage.usage_metadata.prompt_token_count = 100
    real_usage.usage_metadata.cached_content_token_count = 60
    real_usage.usage_metadata.candidates_token_count = 40
    real_usage.usage_metadata.total_token_count = 140
    assert extract_gemini_usage(real_usage) == {
        "prompt_tokens": 100,
        "cached_tokens": 60,
        "completion_tokens": 40,
        "total_tokens": 140,
    }

    t = TurnTelemetry(provider="gemini", model_used="gemini-3.5-flash-lite")
    t.merge_usage({"prompt_tokens": 100, "cached_tokens": 50, "completion_tokens": 20, "total_tokens": 120})
    t.merge_usage({"prompt_tokens": 25, "cached_tokens": 0, "completion_tokens": 10, "total_tokens": 35})
    assert t.to_dict()["prompt_tokens"] == 125
    assert t.to_dict()["cached_tokens"] == 50
    assert t.to_dict()["total_tokens"] == 155

    plan = DeterministicPlanStub().plan("What are the first-line screening tests to confirm hypercortisolism in suspected Cushing syndrome?")
    assert any("Cushing" in q for q in plan.search_queries)

    assert percentile([10.0, 20.0, 30.0, 40.0], 50) == 25.0

    r_ok = CaseEvalResult(
        case_id="c1",
        category="clinical_factual",
        query="q1",
        metrics=StageMetrics(total_ms=100.0, ttft_ms=40.0, prompt_tokens=200, cached_tokens=100, total_tokens=250, provider="gemini", model_used="gemini-3.5-flash-lite"),
        scores={"routing": MetricResult("routing", 1.0, True)},
        overall_score=1.0,
        passed=True,
    )
    r_bad = CaseEvalResult(
        case_id="c2",
        category="table_criteria",
        query="q2",
        metrics=StageMetrics(total_ms=1200.0, ttft_ms=500.0, fallback_triggered=True, provider="offline", model_used="offline-synthesizer"),
        scores={"routing": MetricResult("routing", 0.5, False)},
        overall_score=0.5,
        passed=False,
    )

    base = EvalRunReport(
        run_id="base_1",
        timestamp="2026-11-12T00:00:00+00:00",
        mode="offline",
        judge_mode="offline",
        dataset_name="ds",
        dataset_version="1.0",
        total_cases=1,
        passed_cases=1,
        aggregate_scores=compute_aggregate_scores([r_ok]),
        category_scores=compute_category_scores([r_ok]),
        ops_summary=compute_ops_summary([r_ok]),
        results=[r_ok],
    )
    curr = EvalRunReport(
        run_id="curr_1",
        timestamp="2026-11-12T01:00:00+00:00",
        mode="offline",
        judge_mode="offline",
        dataset_name="ds",
        dataset_version="1.0",
        total_cases=2,
        passed_cases=1,
        aggregate_scores=compute_aggregate_scores([r_ok, r_bad]),
        category_scores=compute_category_scores([r_ok, r_bad]),
        ops_summary=compute_ops_summary([r_ok, r_bad]),
        results=[r_ok, r_bad],
    )
    regs = compare_against_baseline(curr, base)
    assert len(regs) >= 3
    curr.regressions = regs

    json_p, md_p = save_report_artifacts(curr, tmp_path, stem="unit_report")
    assert json_p.exists() and md_p.exists()
    md_text = render_markdown_report(curr)
    assert "Regressions Detected" in md_text
    assert "| `c2` |" in md_text
