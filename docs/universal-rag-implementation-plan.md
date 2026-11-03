# Universal Textbook Intelligence Engine: Implementation & Verification Specification

This document details the engineering specifications, architectural modules, acceptance criteria, and verification results for the **CliniSource Universal Textbook Intelligence Platform**.

---

## 1. System Specifications & Module Overview

```
Module 1: Universal Prompts & Domain-Agnostic Tools
       │
       ▼
Module 2: Universal Column-Aware Diagram Engine & Asset Retention
       │
       ▼
Module 3: Table-First Logic & Zero Synthetic Flowcharts
       │
       ▼
Module 4: Universal Orchestrator & Fast ReAct Engine
       │
       ▼
Module 5: Visual Presentation Layer & Typography Normalization
       │
       ▼
Module 6: Multi-Domain E2E Verification Suite (101 Passed Tests)
```

---

## 2. Implementation Modules

### Module 1: Universal Prompts & Domain-Agnostic Tools

- **Objective**: Establish a domain-agnostic textbook instruction set supporting Medicine, Law, Engineering, Science, and Academia.
- **Components**: `agent/prompts.py`, `agent/tools_spec.py`
- **Specifications**:
  - Direct answer first (2–3 sentences resolving the user inquiry).
  - Format comparisons, criteria, dosings, and classifications into clean Markdown tables.
  - Cite textbook passages strictly using 1-based indices `[1]`, `[2]`.
  - Prohibit synthetic Mermaid flowcharts; mandate tables or numbered sequences ($1 \rightarrow 2 \rightarrow 3$).
  - For generic questions, answer directly with zero search latency and zero tool calls.
- **Universal Tool Definitions**:
  - `get_textbook_structure(keywords, book_slug)`: Searches chapters, TOC, and headings.
  - `get_relevant_chunks(query, book_slug, section_id, limit)`: Fetches granular text passages.
  - `get_media_and_tables(query, book_slug, section_id)`: Fetches figures and tables with captions and semantic descriptions.
- **Verification**: `tests/unit/test_book_router.py`, `tests/integration/test_universal_rag.py` (Passed).

---

### Module 2: Universal Column-Aware Diagram Engine & Asset Retention

- **Objective**: Extract authentic textbook diagram plates with zero bleed into adjacent columns and retain source assets.
- **Components**: `ui/diagrams.py`, `ingestion/pipeline_worker.py`
- **Specifications**:
  - In `ui/diagrams.py`, resolve physical 0-based page directly as `page_start - 1`.
  - Column-aware plate bounding: identify column gutters (`col_x0` to `col_x1`) and clip strictly to the diagram's column boundary.
  - Render crisp 180 DPI JPEGs with 92% quality stored in `ui/static/figures_cache/`.
  - Rejection policy: strictly returns `None` if no authentic vector drawings or raster images exist on the page (zero random text fallbacks).
  - Source PDF retention: uploaded PDFs are preserved in `ingestion/test-books/{book_slug}.pdf`.
- **Verification**: `tests/integration/test_diagram_display.py`, `temp/test_ocp_end_to_end.py` (Passed).

---

### Module 3: Table-First Logic & Zero Synthetic Flowcharts

- **Objective**: Ensure high-reliability procedural representation across web and mobile viewports without syntax crashes.
- **Components**: `ui/static/styles.css`, `ui/static/app.js`, `agent/prompts.py`
- **Specifications**:
  - Synthetic Mermaid flowchart code completely eliminated from frontend parsing and LLM prompts.
  - Responsive styling for Markdown tables with scroll wrappers, clean borders, contrasting headers, and zebra striping.
  - Procedural logic rendered as numbered sequences: `1. Initial Assessment → 2. Fluid Bolus → 3. Insulin Infusion`.
- **Verification**: `tests/integration/test_segment5_ui_ux.py` (Passed).

---

### Module 4: Universal Orchestrator & Fast ReAct Engine

- **Objective**: Orchestrate synchronous and streaming consultation turns with intelligent on-demand retrieval.
- **Components**: `agent/orchestrator.py`, `agent/providers.py`, `agent/offline.py`
- **Specifications**:
  - Google Gemini 2.0 Flash tool-calling ReAct loop with prompt caching.
  - Emits real-time SSE event stream: `plan`, `status`, `tools`, `token`, `citations`, `referenced_books`, `figures`, `done`.
  - Early figure emission: diagrams are emitted right after retrieval so users see visual plates immediately.
  - Client disconnect detection cancels background generation tasks instantly.
  - Local smart synthesizer fallback in `agent/offline.py` for fully offline environments.
- **Verification**: `tests/integration/test_streaming_endpoint.py`, `tests/integration/test_segment3_agent_streaming.py` (Passed).

---

### Module 5: Visual Presentation Layer & Typography Normalization

- **Objective**: Guarantee clean typography, non-colliding citations, and standard mathematical notation across turns.
- **Components**: `agent/sanitizers.py`
- **Specifications**:
  - Sanitizes raw LaTeX tags and eliminates stray dollar signs (`15$`, `35$`).
  - Converts hormone symbols (`T₄`, `TRβ₂`) and ion formulas (`Na⁺/K⁺-ATPase`, `Mg²⁺`) to clean Unicode.
  - Normalizes comparison operators (`≥`, `≤`).
  - Auto-balances Markdown bold markers to eliminate hanging syntax.
  - Transforms publisher bibliography brackets into non-colliding `(Ref X)` text so only real verified citations open the Evidence Drawer.
- **Verification**: `tests/integration/test_ui_typography.py`, `tests/unit/test_citation_normalizer.py` (Passed).

---

### Module 6: Six-Segment Verification Suite

- **Objective**: Validate end-to-end production integrity across all system boundaries.
- **Test Results Summary**:
  ```text
  ============================= test session starts =============================
  platform win32 -- Python 3.11.7, pytest-9.1.1, pluggy-1.6.0
  rootdir: C:\Users\govin\Desktop\projects\Text-Book-RAG
  collected 101 items

  tests\integration\test_auth_api.py .                                     [  0%]
  tests\integration\test_diagram_display.py .                              [  1%]
  tests\integration\test_dynamic_ingestion.py .....                        [  6%]
  tests\integration\test_multi_book_filter.py .                            [  7%]
  tests\integration\test_segment1_ingestion.py ........                    [ 15%]
  tests\integration\test_segment2_retrieval.py ........                    [ 23%]
  tests\integration\test_segment3_agent_streaming.py ........              [ 31%]
  tests\integration\test_segment4_api_isolation.py ........                [ 39%]
  tests\integration\test_segment5_ui_ux.py .........                       [ 48%]
  tests\integration\test_segment6_concurrency_stress.py ........           [ 56%]
  tests\integration\test_sessions_api.py .                                 [ 57%]
  tests\integration\test_step4_harrison_e2e.py .....                       [ 62%]
  tests\integration\test_streaming_endpoint.py .                           [ 63%]
  tests\integration\test_ui_toggles.py ...                                 [ 66%]
  tests\integration\test_ui_typography.py .                                [ 67%]
  tests\integration\test_universal_rag.py .....                            [ 72%]
  tests\integration\test_user_library_page.py .....                        [ 77%]
  tests\unit\test_attending_planner.py ......                              [ 83%]
  tests\unit\test_auth_service.py .                                        [ 84%]
  tests\unit\test_book_router.py ......                                    [ 90%]
  tests\unit\test_citation_normalizer.py ...                               [ 93%]
  tests\unit\test_parallel_figures.py ....                                 [ 97%]
  tests\unit\test_parallel_retrieval.py ..                                 [ 99%]
  tests\unit\test_sessions_service.py .                                    [100%]

  ======================= 101 passed in 688.41s (0:11:28) =======================
  ```
