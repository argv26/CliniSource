"""Aggregation, baseline regression comparison, and JSON/Markdown reporting for LLM Eval Ops."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evals.schema import CaseEvalResult, EvalRunReport


def percentile(values: list[float], pct: float) -> float:
    """Computes linear-interpolated percentile (0..100) for a list of floats."""
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return round(ordered[low], 2)
    frac = rank - low
    return round(ordered[low] * (1.0 - frac) + ordered[high] * frac, 2)


def compute_aggregate_scores(results: list[CaseEvalResult]) -> dict[str, float]:
    """Computes mean metric scores across cases, overall score, and pass rate."""
    if not results:
        return {"overall": 0.0, "pass_rate": 0.0}

    metric_buckets: dict[str, list[float]] = defaultdict(list)
    overall_vals: list[float] = []
    passed_count = 0

    for r in results:
        overall_vals.append(r.overall_score)
        if r.passed:
            passed_count += 1
        for name, m in r.scores.items():
            metric_buckets[name].append(m.score)

    agg: dict[str, float] = {
        "overall": round(sum(overall_vals) / len(overall_vals), 4),
        "pass_rate": round(passed_count / len(results), 4),
    }
    for name in sorted(metric_buckets):
        vals = metric_buckets[name]
        agg[name] = round(sum(vals) / len(vals), 4)
    return agg


def compute_category_scores(results: list[CaseEvalResult]) -> dict[str, dict[str, float]]:
    """Computes per-category count, pass rate, and mean overall score."""
    grouped: dict[str, list[CaseEvalResult]] = defaultdict(list)
    for r in results:
        grouped[r.category].append(r)

    summary: dict[str, dict[str, float]] = {}
    for cat in sorted(grouped):
        items = grouped[cat]
        passed = sum(1 for i in items if i.passed)
        mean_score = sum(i.overall_score for i in items) / len(items)
        summary[cat] = {
            "count": float(len(items)),
            "passed": float(passed),
            "pass_rate": round(passed / len(items), 4),
            "mean_score": round(mean_score, 4),
        }
    return summary


def compute_ops_summary(results: list[CaseEvalResult]) -> dict[str, Any]:
    """Aggregates latency percentiles, token/cache usage, provider usage, and fallback rate."""
    if not results:
        return {}

    total_ms_vals = [r.metrics.total_ms for r in results if r.metrics.total_ms > 0]
    ttft_ms_vals = [r.metrics.ttft_ms for r in results if r.metrics.ttft_ms > 0]
    retrieval_ms_vals = [r.metrics.retrieval_ms for r in results if r.metrics.retrieval_ms > 0]
    planner_ms_vals = [r.metrics.planner_ms for r in results if r.metrics.planner_ms > 0]
    llm_ms_vals = [r.metrics.llm_ms for r in results if r.metrics.llm_ms > 0]

    total_prompt = sum(r.metrics.prompt_tokens for r in results)
    total_cached = sum(r.metrics.cached_tokens for r in results)
    total_completion = sum(r.metrics.completion_tokens for r in results)
    total_tokens = sum(r.metrics.total_tokens for r in results)

    fallback_count = sum(1 for r in results if r.metrics.fallback_triggered)
    error_count = sum(1 for r in results if r.error)

    provider_counts = Counter(r.metrics.provider or "unknown" for r in results)
    model_counts = Counter(r.metrics.model_used or "none" for r in results)

    return {
        "total_ms_mean": round(sum(total_ms_vals) / len(total_ms_vals), 2) if total_ms_vals else 0.0,
        "total_ms_p50": percentile(total_ms_vals, 50),
        "total_ms_p95": percentile(total_ms_vals, 95),
        "ttft_ms_p50": percentile(ttft_ms_vals, 50),
        "ttft_ms_p95": percentile(ttft_ms_vals, 95),
        "retrieval_ms_mean": round(sum(retrieval_ms_vals) / len(retrieval_ms_vals), 2) if retrieval_ms_vals else 0.0,
        "retrieval_ms_p95": percentile(retrieval_ms_vals, 95),
        "planner_ms_mean": round(sum(planner_ms_vals) / len(planner_ms_vals), 2) if planner_ms_vals else 0.0,
        "llm_ms_mean": round(sum(llm_ms_vals) / len(llm_ms_vals), 2) if llm_ms_vals else 0.0,
        "total_prompt_tokens": total_prompt,
        "total_cached_tokens": total_cached,
        "total_completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "cache_hit_ratio": round(total_cached / total_prompt, 4) if total_prompt > 0 else 0.0,
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_count / len(results), 4),
        "error_count": error_count,
        "provider_counts": dict(provider_counts),
        "model_counts": dict(model_counts),
    }


def compare_against_baseline(
    current: EvalRunReport,
    baseline: EvalRunReport,
    max_score_drop: float = 0.05,
    max_p95_regression_ratio: float = 0.25,
) -> list[str]:
    """Compares current run metrics and p95 latency against a saved baseline report."""
    regressions: list[str] = []

    for metric, base_val in baseline.aggregate_scores.items():
        if metric not in current.aggregate_scores:
            continue
        curr_val = current.aggregate_scores[metric]
        delta = curr_val - base_val
        if delta < -max_score_drop:
            regressions.append(
                f"Metric '{metric}' regressed from {base_val:.3f} -> {curr_val:.3f} (delta {delta:+.3f})"
            )

    base_p95 = float(baseline.ops_summary.get("total_ms_p95", 0.0) or 0.0)
    curr_p95 = float(current.ops_summary.get("total_ms_p95", 0.0) or 0.0)
    if base_p95 > 0 and curr_p95 > (base_p95 * (1.0 + max_p95_regression_ratio) + 500.0):
        regressions.append(
            f"Latency p95 regressed from {base_p95:.1f}ms -> {curr_p95:.1f}ms"
        )

    base_fb = float(baseline.ops_summary.get("fallback_rate", 0.0) or 0.0)
    curr_fb = float(current.ops_summary.get("fallback_rate", 0.0) or 0.0)
    if curr_fb - base_fb > 0.05:
        regressions.append(
            f"Fallback rate spiked from {base_fb:.1%} -> {curr_fb:.1%}"
        )

    return regressions


def render_markdown_report(report: EvalRunReport) -> str:
    """Formats an EvalRunReport into a readable Markdown ops scoreboard."""
    lines: list[str] = []
    pass_rate = report.aggregate_scores.get("pass_rate", 0.0)
    overall = report.aggregate_scores.get("overall", 0.0)

    lines.append(f"# CliniSource LLM Eval Ops Report (`{report.run_id}`)")
    lines.append("")
    lines.append(
        f"- **Timestamp**: `{report.timestamp}`\n"
        f"- **Dataset**: `{report.dataset_name}` v`{report.dataset_version}`\n"
        f"- **Mode**: `{report.mode}` | **Judge**: `{report.judge_mode}`\n"
        f"- **Pass Rate**: **{report.passed_cases}/{report.total_cases} ({pass_rate:.1%})** | "
        f"**Mean Overall Score**: **{overall:.3f}**"
    )
    lines.append("")

    if report.regressions:
        lines.append("## Regressions Detected")
        for reg in report.regressions:
            lines.append(f"- **REGRESSION**: {reg}")
        lines.append("")

    lines.append("## Aggregate Quality Scoreboard")
    lines.append("| Metric | Mean Score |")
    lines.append("| :--- | ---: |")
    for k, v in report.aggregate_scores.items():
        lines.append(f"| `{k}` | {v:.4f} |")
    lines.append("")

    ops = report.ops_summary or {}
    lines.append("## LLMOps Latency & Token Economics")
    lines.append("| Operational KPI | Value |")
    lines.append("| :--- | ---: |")
    lines.append(f"| Total Latency p50 / p95 | {ops.get('total_ms_p50', 0):.1f} ms / {ops.get('total_ms_p95', 0):.1f} ms |")
    lines.append(f"| TTFT p50 / p95 | {ops.get('ttft_ms_p50', 0):.1f} ms / {ops.get('ttft_ms_p95', 0):.1f} ms |")
    lines.append(f"| Retrieval Mean / p95 | {ops.get('retrieval_ms_mean', 0):.1f} ms / {ops.get('retrieval_ms_p95', 0):.1f} ms |")
    lines.append(f"| Planner Mean / LLM Mean | {ops.get('planner_ms_mean', 0):.1f} ms / {ops.get('llm_ms_mean', 0):.1f} ms |")
    lines.append(
        f"| Tokens (Prompt / Cached / Completion / Total) | "
        f"{ops.get('total_prompt_tokens', 0)} / {ops.get('total_cached_tokens', 0)} / "
        f"{ops.get('total_completion_tokens', 0)} / {ops.get('total_tokens', 0)} |"
    )
    lines.append(f"| Prompt Cache Hit Ratio | {ops.get('cache_hit_ratio', 0.0):.1%} |")
    lines.append(f"| Fallback Rate | {ops.get('fallback_count', 0)}/{report.total_cases} ({ops.get('fallback_rate', 0.0):.1%}) |")
    lines.append(f"| Providers | `{ops.get('provider_counts', {})}` |")
    lines.append(f"| Models | `{ops.get('model_counts', {})}` |")
    lines.append("")

    lines.append("## Category Breakdown")
    lines.append("| Category | Cases | Passed | Pass Rate | Mean Score |")
    lines.append("| :--- | ---: | ---: | ---: | ---: |")
    for cat, stats in report.category_scores.items():
        lines.append(
            f"| `{cat}` | {int(stats['count'])} | {int(stats['passed'])} | "
            f"{stats['pass_rate']:.1%} | {stats['mean_score']:.3f} |"
        )
    lines.append("")

    failed_or_low = sorted(
        [r for r in report.results if not r.passed or r.overall_score < 0.85],
        key=lambda x: (x.passed, x.overall_score),
    )
    lines.append("## Diagnostic Cases (Failed or < 0.85 Score)")
    if not failed_or_low:
        lines.append("All evaluated cases passed with overall score >= 0.85.")
    else:
        lines.append("| Case ID | Category | Score | Passed | Latency (ms) | Failed Metrics / Error |")
        lines.append("| :--- | :--- | ---: | :---: | ---: | :--- |")
        for r in failed_or_low:
            failed_metrics = [
                f"{k}={m.score:.2f}"
                for k, m in r.scores.items()
                if not m.passed
            ]
            if r.error:
                failed_metrics.append(f"ERROR: {r.error[:80]}")
            diag = ", ".join(failed_metrics) if failed_metrics else "below 0.85 threshold"
            lines.append(
                f"| `{r.case_id}` | `{r.category}` | {r.overall_score:.3f} | "
                f"{'YES' if r.passed else 'NO'} | {r.metrics.total_ms:.1f} | {diag} |"
            )
    lines.append("")
    return "\n".join(lines)


def save_report_artifacts(
    report: EvalRunReport,
    output_dir: str | Path,
    stem: str | None = None,
) -> tuple[Path, Path]:
    """Saves both JSON and Markdown report artifacts and returns (json_path, md_path)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    file_stem = stem or report.run_id
    json_path = out_dir / f"{file_stem}.json"
    md_path = out_dir / f"{file_stem}.md"

    report.save(json_path)
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, md_path
