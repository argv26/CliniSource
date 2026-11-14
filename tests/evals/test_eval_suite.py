"""Pytest Eval Integration Lane validating CliniSource retrieval, offline pipeline, CLI gates, and live LLM ops."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

from evals.cli import main as cli_main
from evals.runner import EvalRunner
from evals.schema import EvalDataset

DATASET_PATH = Path("evals/datasets/clinical_gold.json")


@pytest.mark.eval
def test_retrieval_only_benchmark_gate():
    # AC: Full golden dataset executes in retrieval-only mode against textbook_rag.db with routing >= 0.90, Hit@K >= 0.75, and strict sovereignty.
    # Behavior: EvalRunner(mode='retrieval-only').run(27 cases) -> Evaluates router and FTS5 retrieval -> Meets quality and latency gates with zero errors.
    # @lane: service-integration-e2e
    # @dependency: sqlite
    # Selection evidence: Verifies real SemanticBookRouter + SQLite FTS5 index recall and latency across all 4 textbooks (unmockable by unit tests).
    dataset = EvalDataset.load(DATASET_PATH)
    runner = EvalRunner(mode="retrieval-only")

    t0 = time.perf_counter()
    report = runner.run(dataset)
    elapsed_s = time.perf_counter() - t0

    assert report.total_cases == len(dataset.cases)
    assert report.ops_summary["error_count"] == 0
    assert elapsed_s < 15.0, f"retrieval-only suite took {elapsed_s:.2f}s (expected < 15s)"

    agg = report.aggregate_scores
    assert agg["routing"] >= 0.90
    assert agg["retrieval_hit_at_k"] >= 0.75
    assert agg["retrieval_mrr"] >= 0.45
    assert agg["latency_sla"] == 1.0

    by_id = {r.case_id: r for r in report.results}
    assert by_id["multi-001"].scores["routing"].score == 1.0
    assert by_id["multi-002"].scores["routing"].score == 1.0


@pytest.mark.eval
def test_offline_pipeline_fastpath_and_citation_gate():
    # AC: Offline AgentOrchestrator stream_turn honors conversational fast-path SLA and produces strictly verified inline [N] citations cleanly.
    # Behavior: Run representative fast-path & clinical cases through EvalRunner(mode='offline') -> Zero API calls, fastpath latency < 1s, 100% valid citations.
    # @lane: service-integration-e2e
    # @dependency: sqlite
    # Selection evidence: Exercises full ContextManager, SemanticBookRouter, SQLite retrieval, SSE stream_turn telemetry, and OfflineSynthesizer together.
    dataset = EvalDataset.load(DATASET_PATH)
    runner = EvalRunner(mode="offline", judge_mode="offline", transport="stream")
    selected_ids = ["conv-001", "conv-002", "conv-003", "endo-001", "cornea-001"]

    report = runner.run(dataset, case_ids=selected_ids)
    assert report.total_cases == len(selected_ids)
    assert report.ops_summary["error_count"] == 0
    assert report.ops_summary["fallback_count"] == 0
    assert report.ops_summary["total_tokens"] == 0

    by_id = {r.case_id: r for r in report.results}
    for conv_id in ("conv-001", "conv-002", "conv-003"):
        r = by_id[conv_id]
        assert r.passed is True
        assert r.metrics.provider == "fastpath"
        assert r.metrics.retrieval_ms == 0.0
        assert r.metrics.ttft_ms > 0.0
        assert r.scores["fastpath_scope"].score == 1.0
        assert r.scores["latency_sla"].score == 1.0

    for clin_id in ("endo-001", "cornea-001"):
        r = by_id[clin_id]
        assert r.metrics.provider == "offline"
        assert r.metrics.retrieval_ms > 0.0
        assert r.metrics.ttft_ms > 0.0
        assert r.scores["routing"].score == 1.0
        assert r.scores["retrieval_hit_at_k"].score == 1.0
        assert r.scores["citation_integrity"].score == 1.0


@pytest.mark.eval
def test_cli_baseline_regression_gate(tmp_path: Path):
    # AC: CLI generates JSON/Markdown reports, exits 0 against matching baseline, and exits 1 when regressions breach thresholds.
    # Behavior: Invoke evals.cli.main saving baseline then comparing against matching and inflated strict baselines -> Exact 0 vs 1 exit codes.
    # @lane: service-integration-e2e
    # @dependency: sqlite
    # Selection evidence: Verifies full CLI argument parsing, file emission, and CI exit-code contracts end-to-end.
    baseline_path = tmp_path / "baseline.json"
    out_dir = tmp_path / "reports"

    rc_save = cli_main([
        "--mode", "retrieval-only",
        "--case-id", "endo-001,harrison-001,cornea-001,conv-001",
        "--output-dir", str(out_dir),
        "--stem", "cli_run",
        "--save-baseline", str(baseline_path),
        "--quiet",
    ])
    assert rc_save == 0
    assert baseline_path.exists()
    assert (out_dir / "cli_run.json").exists()
    assert (out_dir / "cli_run.md").exists()

    rc_clean = cli_main([
        "--mode", "retrieval-only",
        "--case-id", "endo-001,harrison-001,cornea-001,conv-001",
        "--baseline", str(baseline_path),
        "--no-save",
        "--quiet",
    ])
    assert rc_clean == 0

    strict_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    strict_payload["aggregate_scores"]["overall"] = 1.0
    strict_payload["aggregate_scores"]["retrieval_mrr"] = 1.0  # drops > 0.05 vs 0.833 on this slice
    strict_path = tmp_path / "strict_baseline.json"
    strict_path.write_text(json.dumps(strict_payload, indent=2), encoding="utf-8")

    rc_reg = cli_main([
        "--mode", "retrieval-only",
        "--case-id", "endo-001,harrison-001,cornea-001,conv-001",
        "--baseline", str(strict_path),
        "--fail-on-regression",
        "--no-save",
        "--quiet",
    ])
    assert rc_reg == 1


@pytest.mark.live_eval
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_EVAL") != "1",
    reason="Live LLM & Judge evals are gated behind RUN_LIVE_EVAL=1 to preserve API quota.",
)
def test_live_llm_and_judge_eval_gate():
    # AC: With RUN_LIVE_EVAL=1, live AgentOrchestrator + LLMJudgeEvaluator execute end-to-end capturing TTFT, tokens, and semantic scores.
    # Behavior: EvalRunner(mode='live', judge_mode='live') on clinical + fastpath cases -> Populates live telemetry & semantic scores cleanly.
    # @lane: service-integration-e2e
    # @dependency: full-system
    # Selection evidence: Verifies live LLM synthesis, real SSE TTFT, token metadata capture, and LLM-as-a-Judge scoring end-to-end.
    load_dotenv()
    assert os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY"), (
        "RUN_LIVE_EVAL=1 requires GEMINI_API_KEY or OPENAI_API_KEY to be set."
    )

    dataset = EvalDataset.load(DATASET_PATH)
    runner = EvalRunner(mode="live", judge_mode="live", transport="stream")
    report = runner.run(dataset, case_ids=["endo-002", "conv-001"])

    assert report.total_cases == 2
    assert report.ops_summary["error_count"] == 0
    assert report.ops_summary["total_tokens"] > 0

    by_id = {r.case_id: r for r in report.results}
    conv = by_id["conv-001"]
    assert conv.passed is True
    assert conv.metrics.provider == "fastpath"

    clin = by_id["endo-002"]
    assert len(clin.reply) >= 80
    assert clin.metrics.ttft_ms > 0.0
    assert clin.scores["routing"].score == 1.0
    assert clin.scores["retrieval_hit_at_k"].score == 1.0
    assert clin.scores["citation_integrity"].score == 1.0
    assert "faithfulness" in clin.scores
    assert "answer_completeness" in clin.scores
    assert "clinical_soundness" in clin.scores
