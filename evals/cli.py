"""Command-line interface for running CliniSource LLM Eval Ops suites and regression gates."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from evals.reporter import save_report_artifacts
from evals.runner import EvalRunner
from evals.schema import CaseEvalResult, EvalDataset, EvalRunReport


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _parse_case_ids(raw_values: list[str] | None) -> list[str] | None:
    if not raw_values:
        return None
    case_ids: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        for part in item.split(","):
            cid = part.strip()
            if cid and cid not in seen:
                seen.add(cid)
                case_ids.append(cid)
    return case_ids or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evals.cli",
        description="Run CliniSource LLM evaluation benchmarks, telemetry checks, and regression gates.",
    )
    parser.add_argument(
        "--dataset",
        default="evals/datasets/clinical_gold.json",
        help="Path to the golden dataset JSON file (default: evals/datasets/clinical_gold.json).",
    )
    parser.add_argument(
        "--mode",
        choices=list(EvalRunner.VALID_MODES),
        default="retrieval-only",
        help="Execution mode: retrieval-only (FTS5 + router), offline (stub + offline synthesizer), or live (full LLM).",
    )
    parser.add_argument(
        "--judge-mode",
        choices=["none", "offline", "live"],
        default=None,
        help="Semantic judge mode (defaults to 'none' in retrieval-only, 'offline' in offline, 'live' in live).",
    )
    parser.add_argument(
        "--transport",
        choices=list(EvalRunner.VALID_TRANSPORTS),
        default="stream",
        help="Orchestrator transport for offline/live modes: stream (SSE, tracks TTFT) or sync (default: stream).",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Optional single category filter (e.g., clinical_factual, table_criteria, anatomy_figure).",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=None,
        help="Filter to specific case ID(s); accepts comma-separated lists or repeated flags.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of filtered cases to execute.",
    )
    parser.add_argument(
        "--output-dir",
        default="evals/reports",
        help="Directory where JSON and Markdown reports are written (default: evals/reports).",
    )
    parser.add_argument(
        "--stem",
        default=None,
        help="Optional filename stem for generated JSON/Markdown reports (defaults to run_id).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip saving timestamped JSON and Markdown artifacts to --output-dir.",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Path to a saved baseline JSON report to compare metrics and latency against.",
    )
    parser.add_argument(
        "--save-baseline",
        nargs="?",
        const="evals/reports/baseline.json",
        default=None,
        help="Save the resulting JSON report as a baseline (default path: evals/reports/baseline.json).",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=None,
        help="Optional minimum required pass rate in [0.0, 1.0]; exits non-zero if not met.",
    )
    parser.add_argument(
        "--min-overall",
        type=float,
        default=None,
        help="Optional minimum required mean overall score in [0.0, 1.0]; exits non-zero if not met.",
    )
    parser.add_argument(
        "--max-score-drop",
        type=float,
        default=0.05,
        help="Maximum tolerated aggregate score drop vs baseline before flagging regression (default: 0.05).",
    )
    parser.add_argument(
        "--max-p95-regression-ratio",
        type=float,
        default=0.25,
        help="Maximum tolerated fractional p95 latency increase vs baseline (default: 0.25).",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Explicitly fail with non-zero exit code on baseline regression or threshold breach (enabled by default).",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Log threshold breaches or baseline regressions as warnings without exiting non-zero.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-case progress lines.",
    )
    return parser


def _print_case_progress(idx: int, total: int, result: CaseEvalResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    failed_names = [k for k, v in result.scores.items() if not v.passed]
    extra = ""
    if result.error:
        extra = f" err={result.error[:60]}"
    elif failed_names:
        extra = f" failed=[{', '.join(failed_names)}]"
    print(
        f"[{idx:>{len(str(total))}}/{total}] {result.case_id:<14} {status} "
        f"score={result.overall_score:.3f} ms={result.metrics.total_ms:.1f}{extra}"
    )


def _print_summary(
    report: EvalRunReport,
    json_path: Path | None,
    md_path: Path | None,
    baseline_saved: Path | None,
    gate_failures: list[str],
) -> None:
    agg = report.aggregate_scores
    ops = report.ops_summary
    print("\n" + "=" * 72)
    print(f"CliniSource Eval Ops Summary | run_id={report.run_id}")
    print("=" * 72)
    print(
        f"Dataset     : {report.dataset_name} v{report.dataset_version} "
        f"({report.passed_cases}/{report.total_cases} passed, "
        f"pass_rate={agg.get('pass_rate', 0.0):.1%}, overall={agg.get('overall', 0.0):.4f})"
    )
    print(f"Execution   : mode={report.mode} | judge={report.judge_mode}")

    metric_items = [
        f"{k}={v:.3f}"
        for k, v in agg.items()
        if k not in ("overall", "pass_rate")
    ]
    if metric_items:
        print(f"Metrics     : {', '.join(metric_items)}")

    print(
        f"Latency     : p50={ops.get('total_ms_p50', 0.0):.1f}ms | "
        f"p95={ops.get('total_ms_p95', 0.0):.1f}ms | "
        f"TTFT p50={ops.get('ttft_ms_p50', 0.0):.1f}ms | "
        f"Retrieval mean={ops.get('retrieval_ms_mean', 0.0):.1f}ms"
    )
    print(
        f"Tokens/Ops  : total={ops.get('total_tokens', 0)} "
        f"(prompt={ops.get('total_prompt_tokens', 0)}, cached={ops.get('total_cached_tokens', 0)}, "
        f"cache_ratio={ops.get('cache_hit_ratio', 0.0):.1%}) | "
        f"fallbacks={ops.get('fallback_count', 0)}/{report.total_cases}"
    )

    if json_path and md_path:
        print(f"Reports     : {json_path} | {md_path}")
    if baseline_saved:
        print(f"Baseline    : saved to {baseline_saved}")

    if report.regressions:
        print("\nRegressions Detected:")
        for reg in report.regressions:
            print(f"  - {reg}")

    if gate_failures:
        print("\nGate Failures:")
        for msg in gate_failures:
            print(f"  - {msg}")


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"[evals.cli] Dataset file not found: {dataset_path}", file=sys.stderr)
        return 2

    try:
        dataset = EvalDataset.load(dataset_path)
    except Exception as exc:
        print(f"[evals.cli] Failed to load dataset '{dataset_path}': {exc}", file=sys.stderr)
        return 2

    baseline_report: EvalRunReport | None = None
    if args.baseline:
        baseline_path = Path(args.baseline)
        if not baseline_path.exists():
            print(f"[evals.cli] Baseline report not found: {baseline_path}", file=sys.stderr)
            return 2
        try:
            baseline_report = EvalRunReport.load(baseline_path)
        except Exception as exc:
            print(f"[evals.cli] Failed to load baseline '{baseline_path}': {exc}", file=sys.stderr)
            return 2

    case_ids = _parse_case_ids(args.case_id)
    selected_cases = dataset.filter(category=args.category, case_ids=case_ids, limit=args.limit)
    if not selected_cases:
        print(
            f"[evals.cli] No cases matched filters (category={args.category}, case_ids={case_ids}, limit={args.limit}).",
            file=sys.stderr,
        )
        return 1

    runner = EvalRunner(
        mode=args.mode,
        judge_mode=args.judge_mode,
        transport=args.transport,
    )

    if not args.quiet:
        print(
            f"Running {len(selected_cases)} eval case(s) from '{dataset.name}' "
            f"[mode={runner.mode}, judge={runner.judge_mode}, transport={runner.transport}]"
        )

    report = runner.run(
        dataset=dataset,
        category=args.category,
        case_ids=case_ids,
        limit=args.limit,
        baseline=baseline_report,
        max_score_drop=args.max_score_drop,
        max_p95_regression_ratio=args.max_p95_regression_ratio,
        progress_cb=None if args.quiet else _print_case_progress,
    )

    json_path: Path | None = None
    md_path: Path | None = None
    if not args.no_save:
        json_path, md_path = save_report_artifacts(report, args.output_dir, stem=args.stem)

    baseline_saved: Path | None = None
    if args.save_baseline:
        baseline_saved = Path(args.save_baseline)
        report.save(baseline_saved)

    gate_failures: list[str] = []
    pass_rate = report.aggregate_scores.get("pass_rate", 0.0)
    overall = report.aggregate_scores.get("overall", 0.0)
    if args.min_pass_rate is not None and pass_rate < args.min_pass_rate:
        gate_failures.append(
            f"pass_rate {pass_rate:.4f} is below required --min-pass-rate {args.min_pass_rate:.4f}"
        )
    if args.min_overall is not None and overall < args.min_overall:
        gate_failures.append(
            f"overall score {overall:.4f} is below required --min-overall {args.min_overall:.4f}"
        )
    if report.regressions:
        gate_failures.extend(report.regressions)

    _print_summary(report, json_path, md_path, baseline_saved, gate_failures)

    if gate_failures and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
