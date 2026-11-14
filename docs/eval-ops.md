# CliniSource LLM Evaluation & Ops Framework (`evals/`)

This guide documents the **LLM Evaluation Test Suite & Ops** system built for **CliniSource** (`Text-Book-RAG`) to continuously measure retrieval precision, citation integrity, clinical generation quality, formatting compliance, and operational telemetry across development and pre-release workflows.

---

## 1. Architecture Overview

The framework is separated into four layers so fast deterministic checks can run in seconds without API spend while live LLM and LLM-as-a-Judge checks share the exact same schemas and reporting pipeline:

```
evals/datasets/clinical_gold.json (27 curated cases, 4 textbooks, 7 categories)
   │
   ▼
evals/runner.py (EvalRunner: retrieval-only | offline | live)
   ├── retrieval-only ──► SemanticBookRouter + _execute_parallel_retrieval (FTS5)
   ├── offline        ──► AgentOrchestrator(OfflineSynthesizer) + Stub Planner
   └── live           ──► AgentOrchestrator(Gemini/OpenAI + AttendingPlanner)
   │
   ├──► Deterministic Evaluators (evals/evaluators/deterministic.py)
   │      routing, Hit@K, MRR, keyword_coverage, citation_integrity,
   │      format_compliance, fastpath_scope, figure_presence, latency_sla
   │
   ├──► Semantic Evaluators (evals/evaluators/llm_judge.py)
   │      faithfulness, answer_completeness, clinical_soundness (live | offline)
   │
   └──► evals/reporter.py + evals/cli.py
          JSON trace + Markdown scoreboard, p50/p95 KPIs, baseline diffing
```

---

## 2. Package Layout & Instrumentation

| File / Module | Purpose |
| :--- | :--- |
| `evals/schema.py` | Dataclasses (`EvalCase`, `EvalDataset`, `StageMetrics`, `MetricResult`, `CaseEvalResult`, `EvalRunReport`) and JSON loaders/savers. |
| `evals/datasets/clinical_gold.json` | 27-case golden benchmark verified against `textbook_rag.db`. |
| `evals/evaluators/deterministic.py` | Zero-API deterministic scorers returning `[0.0, 1.0]` normalized scores, pass flags, and diagnostic metadata. |
| `evals/evaluators/llm_judge.py` | `LLMJudgeEvaluator` supporting structured JSON Gemini/OpenAI judging (`mode="live"`) and deterministic token/fact-overlap heuristics (`mode="offline"`). |
| `evals/runner.py` | `EvalRunner` executing `retrieval-only`, `offline`, and `live` pipelines over `stream` (SSE with TTFT) or `sync` transports, with `DeterministicPlanStub` and chunk hydration. |
| `evals/reporter.py` | Percentile (`p50`/`p95`) latency aggregation, token/cache economics, baseline comparison, and Markdown/JSON artifact generation. |
| `evals/cli.py` | CLI entrypoint (`python -m evals.cli`) with filtering, baseline saving/comparison, and CI regression gates. |
| `evals/reports/` | Output directory for timestamped `.json`/`.md` artifacts (gitignored) and tracked `baseline.json`. |
| `agent/telemetry.py` | `TurnTelemetry` dataclass and safe `MagicMock`-resistant token/cache extractors (`extract_gemini_usage`, `extract_openai_usage`). |
| `agent/orchestrator.py` / `planner.py` / `providers.py` / `offline.py` | Non-invasive additive `"telemetry"` and `"routed_books"` payloads emitted on `run_turn()` return dicts and `stream_turn()` `done` events. |

---

## 3. Golden Benchmark Dataset (`clinical_gold.json`)

The default benchmark (`clinisource_clinical_gold_v1`, v`1.0.0`) covers all 4 indexed textbooks in `textbook_rag.db` plus conversational and guardrail edge cases:

| Category | Count | Focus & Assertions Tested |
| :--- | ---: | :--- |
| `clinical_factual` | 9 | Mechanism, workup, diagnosis, and anatomy questions across Harrison, Williams, Cornea, and A&P 2e. |
| `table_criteria` | 5 | Structured diagnostic criteria / comparisons requiring Markdown tables (`require_table=true`). |
| `anatomy_figure` | 4 | Pathways and structural topics expecting retrieved figure plates (`require_figures=true`). |
| `differential_diagnosis` | 3 | Cross-entity clinical differentiation requiring structured comparisons and multi-book synthesis. |
| `multi_book` | 2 | User Selection Sovereignty checks where explicit `active_books` must be preserved identically. |
| `conversational_fastpath` | 3 | Greetings, gratitude, and meta inquiries (`hello`, `thank you!`, `what model are you?`) enforcing 0 tool calls and `< 1000 ms` latency. |
| `out_of_scope` | 1 | Non-medical tax query testing honest abstention without fabricated textbook citations. |

---

## 4. Metrics & Evaluation Rubrics

### Deterministic Metrics (`[0.0, 1.0]`)
- **`routing`**: Checks `SemanticBookRouter` recall against `expected_books`. When `active_books` is specified, enforces strict set equality (`sovereignty_preserved`) to verify User Selection Sovereignty.
- **`retrieval_hit_at_k`** (`k=6`): `1.0` if at least one top-K chunk from an expected book matches `ceil(len(expected_keywords) / 2)` expected keywords; otherwise `0.0`.
- **`retrieval_mrr`**: Reciprocal rank (`1 / rank`) of the first relevant chunk in top-K. Diagnostic `details` also tracks `references_chunks_in_top_k`.
- **`retrieval_keyword_coverage`**: Fraction of `expected_keywords_in_chunks` present across top-K retrieved headings and texts (`passed >= 0.66`).
- **`figure_presence`**: Present when `require_figures=True`; passes if retrieved/emitted figures list is non-empty.
- **`citation_integrity`**: Verifies every inline `[N]` pill maps to a verified `CitationRecord` (`phantom_ids == []`) and at least one valid citation pill appears when `require_citations=True`. Zero citations enforced on conversational cases.
- **`format_compliance`**:
  - Hard zero-score/fail gate if a synthetic ` ```mermaid ` block appears.
  - Fails on stray `$` typography (`15$`), raw `\text{...}` LaTeX, or missing Markdown table when `require_table=True`.
  - Checks Direct Answer First opening (no filler like *"Sure, here is..."*) and balanced `**` bold markers.
- **`fastpath_scope`**: Verifies `0` tool calls & non-empty reply on conversational cases, explicit abstention phrases on `out_of_scope` cases, and reply length `>= 80` chars on clinical queries.
- **`latency_sla`**: `1.0` when `total_ms <= max_latency_ms`; linear decay down to `0.0` at `2 * max_latency_ms`.

### Semantic Judge Metrics (`LLMJudgeEvaluator`)
Scored on a `1`–`5` integer rubric normalized via `(score - 1) / 4.0` (`passed >= 0.75`, i.e., `>= 4/5`):
1. **`faithfulness`**: Whether clinical claims, lab cutoffs, and dosages are strictly supported by retrieved textbook chunks (flags unsupported numbers or extrapolation).
2. **`answer_completeness`**: Coverage of `expected_answer_points`.
3. **`clinical_soundness`**: Medical accuracy, safety, and appropriate scoping/abstention.

Live judge configuration:
- Controlled via `EVAL_JUDGE_MODEL` (defaults to `gemini-3.5-flash-lite`, with fallbacks `gemini-3.1-flash-lite`, `gemini-3.5-flash`, `gemini-2.5-flash`, or OpenAI `gpt-4o-mini` if only `OPENAI_API_KEY` is configured).

---

## 5. LLMOps Operational Telemetry

Every `run_turn()` / `stream_turn()` execution captures `TurnTelemetry`:
- **Stage Latencies**: `planner_ms`, `routing_ms`, `retrieval_ms`, `ttft_ms` (measured to first streamed token delta), `llm_ms`, `total_ms`.
- **Provider & Resilience**: `provider`, `model_used`, `fallback_triggered`, `fallback_reason`, `react_iterations`.
- **Token & Context Cache Economics**: `prompt_tokens`, `cached_tokens` (from Gemini `cached_content_token_count` / OpenAI `cached_tokens`), `completion_tokens`, `total_tokens`, plus aggregate `cache_hit_ratio`.

---

## 6. CLI Operations & Regression Gates

Run via the project virtual environment (`.venv\Scripts\python.exe`):

```powershell
# 1. Fast retrieval & router benchmark (~3-4s, 0 API calls)
.venv\Scripts\python.exe -m evals.cli --mode retrieval-only

# 2. Save a verified baseline snapshot
.venv\Scripts\python.exe -m evals.cli --mode retrieval-only --save-baseline

# 3. Run regression check against baseline (exits 1 if metric drop > 0.05 or p95 latency spikes > 25% + 500ms)
.venv\Scripts\python.exe -m evals.cli --mode retrieval-only --baseline evals/reports/baseline.json

# 4. Full local orchestrator + offline heuristic judge (0 API calls)
.venv\Scripts\python.exe -m evals.cli --mode offline --judge-mode offline

# 5. Live LLM synthesis + live LLM-as-a-Judge check on specific cases
$env:GEMINI_MODEL='gemini-3.5-flash-lite'
.venv\Scripts\python.exe -m evals.cli --mode live --judge-mode live --case-id endo-001,endo-002,conv-001
```

### Common CLI Flags
- `--mode [retrieval-only|offline|live]` (default: `retrieval-only`)
- `--judge-mode [none|offline|live]` (defaults to matching mode, or `none` for `retrieval-only`)
- `--transport [stream|sync]` (default: `stream`)
- `--category <name>`, `--case-id <id1,id2>`, `--limit <N>`
- `--baseline <path>`, `--save-baseline [path]` (default path: `evals/reports/baseline.json`)
- `--min-pass-rate <0..1>`, `--min-overall <0..1>`, `--max-score-drop <float>`, `--max-p95-regression-ratio <float>`
- `--fail-on-regression` (active whenever `--baseline` is given), `--warn-only`, `--no-save`, `--quiet`

---

## 7. Pytest Integration & CI Lanes

Registered in `pytest.ini` (`@pytest.mark.eval` and `@pytest.mark.live_eval`):

```powershell
# Fast unit + deterministic evaluation gates (runs cleanly in CI with 0 API quota)
.venv\Scripts\python.exe -m pytest tests/unit/test_eval_evaluators.py tests/evals/test_eval_suite.py

# Live end-to-end LLM & Judge lane (skipped cleanly unless RUN_LIVE_EVAL=1)
$env:RUN_LIVE_EVAL='1'; $env:GEMINI_MODEL='gemini-3.5-flash-lite'
.venv\Scripts\python.exe -m pytest tests/evals/test_eval_suite.py -m live_eval -v
```

### Baseline Findings Tracked by the Suite
Initial runs across the 27-case benchmark surfaced concrete product behaviors that the eval suite continues to monitor without suppression:
1. **`agent/offline.py`**: Legacy canned responses contain ` ```mermaid ` blocks (`endo-003`, `endo-006`) and a `"thyroid"` substring collision matching `"parathyroid"` (`multi-001`).
2. **`retrieval/sqlite.py`**: Heading-based spell correction can drift terms absent from headings (e.g., `"femoral"` on `anat-004`), and bibliography `"References"` chunks can rank in top-K for ophthalmology queries.
3. **`agent/orchestrator.py`**: Default deprecated `gemini-2.0-flash` / `1.5-flash` candidates trigger `404 NOT_FOUND` fallbacks unless `GEMINI_MODEL` is set to an active model such as `gemini-3.5-flash-lite`.
