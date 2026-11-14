# LLM Evaluation & Ops Implementation Plan (`evals/`)

This document tracks the approved incremental implementation plan, task prompts, acceptance criteria, and verification results for the **CliniSource LLM Evaluation Test Suite & Ops** framework.

---

## Implementation Progress Summary

| Step | Module / Scope | Status | Verification Summary |
|---|---|---|---|
| **Step 1** | Golden Benchmark Schema & Curated Dataset (`evals/schema.py`, `evals/datasets/clinical_gold.json`) | **Completed** | 27 verified cases across 7 categories & 4 indexed books; JSON round-trip & schema validation verified. |
| **Step 2** | Non-Invasive Pipeline Telemetry (`agent/telemetry.py`, orchestrator/provider hooks) | **Completed** | 37 unit & streaming integration tests passed; fastpath, offline & mock safety checks verified. |
| **Step 3** | Deterministic Retrieval, Citation & Format Evaluators (`evals/evaluators/deterministic.py`) | **Completed** | Routing, Hit@K, MRR, citation integrity, format, figure & SLA checks verified across positive/negative cases. |
| **Step 4** | LLM-as-a-Judge & Offline Heuristic Evaluators (`evals/evaluators/llm_judge.py`) | **Completed** | Offline heuristic, fenced JSON parsing, mock & live Gemini judge verified. |
| **Step 5** | Ops Eval Runner, Regression Gates & Report Generator (`evals/runner.py`, `reporter.py`, `cli.py`) | **Completed** | Verified `retrieval-only` (<4s), `offline` (0 API calls), `live` (default fallback & `gemini-3.5-flash-lite` 0.976), and `--baseline` regression gates. |
| **Step 6** | Pytest Eval Integration Lane & `docs/eval-ops.md` (`tests/evals/`, `tests/unit/`) | **Completed** | `10 passed, 1 skipped` in eval lane; `1 passed` under `RUN_LIVE_EVAL=1 -m live_eval`; full repo suite `112 passed, 1 skipped`. |

---

## Step-by-Step Plan & Verification Log

### Step 1: Golden Benchmark Schema & Curated Dataset (Completed)
- **Artifacts Created**:
  - `evals/__init__.py`
  - `evals/schema.py` (`EvalCase`, `EvalDataset`, `StageMetrics`, `MetricResult`, `CaseEvalResult`, `EvalRunReport`)
  - `evals/datasets/clinical_gold.json` (27 cases: 9 `clinical_factual`, 5 `table_criteria`, 4 `anatomy_figure`, 3 `differential_diagnosis`, 2 `multi_book`, 3 `conversational_fastpath`, 1 `out_of_scope`)
  - Exploratory probe script (reusable in `temp/`): `temp/probe_eval_topics.py`
- **Verification Results**:
  - Dataset load & category coverage verified (`27` cases across all 4 textbooks in `textbook_rag.db`).
  - Schema validation (invalid category rejection, duplicate ID rejection), score clamping (`[0.0, 1.0]`), filtering, and JSON round-trip serialization (`EvalRunReport.save` / `.load`) passed under `.venv\Scripts\python.exe`.
  - Spot-checked FTS5 chunk retrieval against `Williams_Textbook_of_Endocrinology_15th_edition_2` and `Harrison_2025_22nd_Edition` (`3` hits each).
  - Existing unit test suite regression check: `.venv\Scripts\python.exe -m pytest tests/unit/` — `23 passed in 13.33s`.
  - **Baseline Observations During Probe**: Identified real retrieval latency/accuracy baselines to track in Ops (e.g., `OR` scan latency on `heart failure ejection fraction`, spell-correction drift on `femoral triangle`, and `References` chunks ranking high in `Cornea`).

### Step 2: Non-Invasive Pipeline Telemetry & LLMOps Instrumentation (Completed)
- **Artifacts Created / Modified**:
  - Created `agent/telemetry.py` (`TurnTelemetry`, `_safe_int`, `extract_gemini_usage`, `extract_openai_usage`).
  - Modified `agent/planner.py` (records `last_telemetry` with `planner_ms`, provider, model, and usage tokens).
  - Modified `agent/providers.py` (`run_openai_turn` and `run_gemini_turn` accumulate `llm_ms`, `retrieval_ms`, `react_iterations`, `model_used`, and token/cached counts).
  - Modified `agent/offline.py` (`run_offline_synthesizer_turn` records `retrieval_ms` and offline/fastpath provider tag).
  - Modified `agent/orchestrator.py` (`run_turn` and `stream_turn` emit additive `"telemetry"` and `"routed_books"` fields, including `ttft_ms` on first token and `fallback_triggered` status).
- **Verification Results**:
  - `.venv\Scripts\python.exe -m pytest tests/unit/ tests/integration/test_segment3_agent_streaming.py tests/integration/test_streaming_endpoint.py tests/integration/test_universal_rag.py` — `37 passed in 93.44s`.
  - Fast-path `run_turn("hello")` & `stream_turn("hello")`: `provider="fastpath"`, `retrieval_ms=0.0`, `total_ms < 500` on `run_turn`, `ttft_ms` recorded on `stream_turn`.
  - Offline clinical turn (with mock planner): `provider="offline"`, `retrieval_ms > 0`, `ttft_ms > 0`, `routed_books` preserved.
  - Mock safety verified: `MagicMock` responses yield `0` tokens without crashing or inflating counts.

### Step 3: Deterministic Retrieval, Routing, Citation & Format Evaluators (Completed)
- **Artifacts Created**:
  - `evals/evaluators/__init__.py`
  - `evals/evaluators/deterministic.py` (`score_routing`, `score_retrieval`, `score_citation_integrity`, `score_format_compliance`, `score_fastpath_and_scope`, `score_figures`, `score_latency_sla`, `evaluate_deterministic`)
  - Reusable verification script: `temp/verify_step3_evaluators.py`
- **Verification Results**:
  - `.venv\Scripts\python.exe temp/verify_step3_evaluators.py` — All positive and negative edge-case checks passed (routing sovereignty, Hit@K, MRR rank 2 + References tracking, phantom `[99]` detection, `mermaid` zero-score gate, stray `$` & raw `\text{...}` detection, missing table failure, conversational fast-path, out-of-scope disclosure, figure requirement, latency SLA decay).
  - Existing unit test suite: `.venv\Scripts\python.exe -m pytest tests/unit/` — `23 passed in 14.74s`.

### Step 4: LLM-as-a-Judge & Offline Heuristic Evaluators (Completed)
- **Artifacts Created / Modified**:
  - Created `evals/evaluators/llm_judge.py` (`LLMJudgeEvaluator`, `_normalize_1_to_5`, `_JUDGE_SYSTEM_PROMPT`).
  - Modified `evals/evaluators/__init__.py` (exports `LLMJudgeEvaluator`).
  - Reusable verification script: `temp/verify_step4_judge.py`.
- **Verification Results**:
  - `.venv\Scripts\python.exe temp/verify_step4_judge.py`:
    - Offline heuristic: supported answer scored `1.0` (`passed=True`), hallucinated answer scored `0.0` (`passed=False`), conversational fast-path skipped cleanly (`1.0`), out-of-scope honesty verified (`1.0` vs `0.0`).
    - Mocked fenced JSON parsing & telemetry verified.
    - Live Gemini Judge (`gemini-3.5-flash-lite`, `1802 ms`, `793` tokens): supported answer scored `1.0` across all 3 dimensions; hallucinated answer scored `0.0` across all 3 dimensions with accurate clinical rationales.
  - Note: Updated default `EVAL_JUDGE_MODEL` fallback list to `gemini-3.5-flash-lite` / `gemini-3.1-flash-lite` / `gemini-3.5-flash` / `gemini-2.5-flash` after live check revealed `gemini-2.0-flash-lite` returning 404 NOT_FOUND.
  - Existing unit test suite: `.venv\Scripts\python.exe -m pytest tests/unit/` — `23 passed`.

### Step 5: Ops Eval Runner, Regression Gates & Report Generator (Completed)
- **Artifacts Created / Modified**:
  - Created `evals/runner.py` (`EvalRunner`, `DeterministicPlanStub`, `_extract_retrieved_chunks`)
  - Created `evals/reporter.py` (`percentile`, `compute_aggregate_scores`, `compute_category_scores`, `compute_ops_summary`, `compare_against_baseline`, `render_markdown_report`, `save_report_artifacts`)
  - Created `evals/cli.py` (`python -m evals.cli` entrypoint supporting `--mode`, `--judge-mode`, `--transport`, `--category`, `--case-id`, `--limit`, `--baseline`, `--save-baseline`, `--min-pass-rate`, `--min-overall`, `--max-score-drop`, `--max-p95-regression-ratio`, `--fail-on-regression`, `--warn-only`)
  - Created `evals/reports/.gitkeep`, initial `evals/reports/baseline.json` (`retrieval-only`), and updated `.gitignore` (ignores timestamped reports while tracking `.gitkeep` and `baseline.json`).
  - Reusable verification / inspection scripts in `temp/`: `temp/inspect_stub_queries.py`, `temp/verify_step5_ops.py` (temporary fixture `temp/synthetic_strict_baseline.json`).
- **Verification Results**:
  - `retrieval-only` (27 cases): exited `0` in ~4s (`21/27` passed, `77.8%` pass rate, overall `0.8248`, `routing=0.982`, `retrieval_hit_at_k=0.815`, `p50=38.8ms`, `p95=151.6ms`), generating `.json` & `.md` artifacts in `evals/reports/`.
  - `offline` (27 cases, zero API calls): exited `0` (`4/27` passed, overall `0.7812`, `citation_integrity=1.000`, `TTFT p50=77.2ms`, `p95=2612.7ms`, `0` fallbacks). Faithfully surfaced `agent/offline.py` gaps (`mermaid` blocks on `endo-003`/`endo-006`, substring `"thyroid"` false-matching `"parathyroid"` in `multi-001`, missing table outputs, and `oos-001` non-abstention).
  - `live` (3 cases `--limit 3`):
    - With default config (`GEMINI_MODEL=gemini-2.0-flash`): surfaced real `404 NOT_FOUND` on deprecated models (`gemini-2.0-flash`, `1.5-flash`, `2.0-flash-lite`) with `fallback_rate=3/3` (`100%`) while `AttendingPlanner` (`gemini-3.5-flash-lite`, `1433` tokens) still achieved `1.000` Hit@K/MRR/figures; `TTFT p50=5267.2ms`.
    - With `$env:GEMINI_MODEL='gemini-3.5-flash-lite'`: `fallbacks=0/3`, overall `0.9756` (`2/3` passed; `faithfulness=1.000`, `answer_completeness=1.000`, `clinical_soundness=1.000`, `format_compliance=1.000`, `total_tokens=19210`, `p50=5873.9ms`, `TTFT p50=4241.6ms`), and caught `[1000, 0994]` non-1-based citation drift on `endo-001`.
  - Regression gates (`temp/verify_step5_ops.py`): clean `--baseline evals/reports/baseline.json` exited `0`; synthetic regression baseline (`--fail-on-regression`) exited `1`; `--min-pass-rate 0.99` exited `1`; `--warn-only` exited `0`; missing dataset exited `2`; unmatched filters exited `1`.
  - Existing unit test suite: `.venv\Scripts\python.exe -m pytest tests/unit/` — `23 passed in 12.84s`.

### Step 6: Pytest Eval Integration Lane & `docs/eval-ops.md` (Completed)
- **Artifacts Created**:
  - `pytest.ini` (registers `@pytest.mark.eval` and `@pytest.mark.live_eval`)
  - `tests/unit/test_eval_evaluators.py` (7 unit tests covering schema/dataset, routing & sovereignty, IR metrics, citation/format corruption gates, offline/mocked LLM judge, telemetry extractors, plan stub, and reporter)
  - `tests/evals/test_eval_suite.py` (3 default `@pytest.mark.eval` integration gates against `textbook_rag.db` + 1 `@pytest.mark.live_eval` gate behind `RUN_LIVE_EVAL=1`)
  - `docs/eval-ops.md` (architecture, dataset categories, metric rubrics, CLI flags, baseline/regression gates, pytest CI commands, and initial baseline insights)
- **Verification Results**:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_eval_evaluators.py tests/evals/test_eval_suite.py -v` — `10 passed, 1 skipped in 6.95s` (0 API spend).
  - `$env:RUN_LIVE_EVAL='1'; $env:GEMINI_MODEL='gemini-3.5-flash-lite'; .venv\Scripts\python.exe -m pytest tests/evals/test_eval_suite.py -m live_eval -v` — `1 passed, 3 deselected in 12.14s`.
  - Full repository suite `.venv\Scripts\python.exe -m pytest -q` — `113 passed, 1 skipped in 1376.61s` (zero regressions).

---

## Post-Fix Verification & Production Baseline Refresh

Following the implementation of targeted fixes across the retrieval, agent, and offline synthesis pipelines:
1. **Active Gemini Model Resolution & Citation Hardening**:
   - `resolve_gemini_candidate_models()` implemented in `agent/providers.py` and `agent/orchestrator.py` dynamically selecting active models (`gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-2.5-flash`, `gemini-3.1-flash-lite`).
   - `_sanitize_citations()` in `agent/sanitizers.py` hardened against bracket lists `[1, 2]` and out-of-range lists `[1000, 0994]`.
2. **FTS5 Spell-Correction & Retrieval Optimization**:
   - `_correct_spelling()` in `retrieval/sqlite.py` now validates candidate words against `chunks_fts` before applying `difflib`, eliminating false spell-correction of real medical terms (`femoral`, `nephron`).
   - References and Bibliography chunks demoted below substantive clinical text in `retrieval/sqlite.py`.
   - Single-term keyword expansion in `retrieval/parallel.py` discovering verified anatomical figures (`FIGURE 25.17 Locations of Secretion and Reabsorption in the Nephron`).
3. **Offline Synthesizer Enhancements**:
   - Replaced legacy `mermaid` blocks with structured Markdown tables in `agent/offline.py`.
   - Fixed regex boundaries to prevent false-matching of `"thyroid"` in `"parathyroid"` and Cornea queries.
   - Added honest out-of-scope abstention (`oos-001`) and automatic Markdown table formatting.
4. **Final Baseline Refresh & E2E Verification**:
   - `evals/cli.py --mode retrieval-only --save-baseline` refreshed `evals/reports/baseline.json`:
     - **Pass Rate**: `88.9%` (24/27 passed) vs initial `77.8%`.
     - **Overall Score**: `0.8740` vs initial `0.8248`.
     - **Retrieval Hit@K**: `0.889` vs initial `0.815`.
     - **Retrieval MRR**: `0.625` vs initial `0.551`.
     - **Figure Presence**: `0.800` vs initial `0.600`.
     - **p95 Latency**: `110.8ms`.
   - Full test suite execution: **113 passed, 1 skipped** (with live eval gate passing 100% on live tests).
   - Temporary scratch scripts in `temp/` cleaned up.
