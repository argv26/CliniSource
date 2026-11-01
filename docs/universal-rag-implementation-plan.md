# Universal Textbook RAG: Incremental Implementation Plan

This implementation plan details the step-by-step transition of CliniSource into a **Universal, Multi-Domain Textbook RAG Engine** (supporting Medicine, Law, Engineering, Science, etc.). It removes hardcoded medical assumptions, completely eliminates fragile synthetic flowcharts (Mermaid), establishes a dedicated **Visual Presentation Layer**, and enables **Reference On-Demand** powered by **Google Gemini 2.0 Flash (Free Tier)**.

---

## Plan Overview & Dependency Graph

```
Step 1: Universal Prompts & Domain-Agnostic Tools
       │
       ▼
Step 2: Universal Diagram Engine & Upload Retention
       │
       ▼
Step 3: Frontend Cleanup (Table CSS & Remove Mermaid Flowcharts)
       │
       ▼
Step 4: Generic Orchestrator & Free Gemini 2.0 Flash ReAct Engine
       │
       ▼
Step 5: Codebase Cleanup (Retire Medical Planners & Update Docs)
       │
       ▼
Step 6: Universal E2E Test Suite Across All Books
```

---

## Step 1: Universal System Prompt & Domain-Agnostic Tools

### 1. Description & Why
Replace the hardcoded medical-only prompt (`INVARIANT_SYSTEM_PROMPT` which forced 2,000-word monographs with 6 mandatory headings) with a universal, domain-agnostic textbook prompt. Expose 3 clean generic tools: `get_textbook_structure`, `get_relevant_chunks`, and `get_media_and_tables` (with semantic captions and descriptions).

### 2. Self-Contained Prompt for Fresh Agent Session
```text
Task: Update `agent/prompts.py` and `agent/tools_spec.py` to support Universal Multi-Domain Textbook RAG.
1. In `agent/prompts.py`:
   - Replace `INVARIANT_SYSTEM_PROMPT` and `SYSTEM_PROMPT` with a universal instruction:
     - Direct answer first (2-3 sentences resolving user query).
     - Format comparisons, criteria, workflows, and classifications into clean Markdown tables.
     - Cite textbook passages strictly using 1-based indices [1], [2] when referencing retrieved chunks.
     - Never emit synthetic Mermaid flowcharts. Use Markdown tables or numbered sequences (1 -> 2 -> 3) for procedural logic.
     - For generic questions (greetings, general definitions), answer directly without calling retrieval tools.
2. In `agent/tools_spec.py`:
   - Define 3 universal tools in `TOOL_DEFINITIONS`:
     - `get_textbook_structure(keywords: str, book_slug: str | None)`: Searches chapters, TOC, and headings.
     - `get_relevant_chunks(query: str, book_slug: str | None, section_id: int | None, limit: int)`: Fetches granular text passages.
     - `get_media_and_tables(query: str, book_slug: str | None, section_id: int | None)`: Fetches figures and tables with captions and semantic descriptions.
   - Maintain backward-compatible aliases for legacy tool names (`search_chunks`, `search_sections`, `search_figures`).
```

### 3. Relevant Files & Dependencies
* Files: `agent/prompts.py`, `agent/tools_spec.py`
* Dependencies: None

### 4. Acceptance Criteria
* `agent/prompts.py` contains zero medical-only monograph mandates.
* `agent/tools_spec.py` exposes `get_textbook_structure`, `get_relevant_chunks`, and `get_media_and_tables`.
* Existing tool callers remain backward-compatible.

### 5. Human-Verifiable Steps
* Run `python -c "from agent.tools_spec import TOOL_DEFINITIONS; print([t['function']['name'] for t in TOOL_DEFINITIONS])"` → Asserts new tool names are present.

---

## Step 2: Universal Diagram Engine & Upload Retention

### 1. Description & Why
Fix the diagram extraction engine in `ui/diagrams.py` by resolving the physical 0-based page directly as `page_start - 1` (fixing the +196 page jump), eliminate false fallback to Anatomy PDF when Harrison/Williams is missing, and ensure `ingestion/pipeline_worker.py` retains uploaded PDFs in `ingestion/test-books/{book_slug}.pdf` before cleanup.

### 2. Self-Contained Prompt for Fresh Agent Session
```text
Task: Fix diagram coordinate resolution and source PDF retention.
1. In `ui/diagrams.py`:
   - In `get_figure_image_path()`, set `pdf_page_idx = max(0, int(page_start) - 1)` directly (chunks.page_start is already 1-based physical PDF page). Do NOT call `pm.printed_to_pdf()`.
   - In `_resolve_pdf_path()`, return None when matching PDF is not found. Do NOT return candidates[0] (which falsely returned Anatomy PDF for other books).
   - Improve figure caption matching regex to handle varied publisher styles: `r"^\s*(?:[•·\-\*]\s*)?(FIG(?:URE)?\.?\s*[\d\.]+[A-Za-z]?)"`.
2. In `ingestion/pipeline_worker.py`:
   - Before unlinking the uploaded PDF in staging, copy it to `ingestion/test-books/{book_slug}.pdf` if not already present.
```

### 3. Relevant Files & Dependencies
* Files: `ui/diagrams.py`, `ingestion/pipeline_worker.py`
* Dependencies: PyMuPDF (`fitz`), Pillow (`PIL`)

### 4. Acceptance Criteria
* Williams Fig. 16.2 resolves to physical PDF page 800 and crops the VTE risk plate accurately.
* When a book PDF is missing, returns `None` and falls back cleanly to the card preview without showing unrelated book images.
* Newly uploaded PDFs are preserved in `ingestion/test-books/`.

### 5. Human-Verifiable Steps
* Run `python temp/test_diagram_engine.py` → Asserts Williams Fig. 16.1, 16.2, 16.3, 16.4 and Anatomy Fig. 1.1 crop properly into `ui/static/figures_cache/`.

---

## Step 3: Frontend UI Streamlining & Table Styling (Remove Flowcharts)

### 1. Description & Why
Remove synthetic Mermaid flowcharts from the frontend completely to eliminate syntax errors, unquoted pipe crashes, giant distorted diamonds, and bomb icons. Add modern, accessible styling for Markdown tables in `ui/static/styles.css`.

### 2. Self-Contained Prompt for Fresh Agent Session
```text
Task: Streamline frontend UI, add table styling, and remove Mermaid flowcharts.
1. In `ui/static/styles.css`:
   - Add `.prose-custom table` styles: full width, clean border `#e2e8f0`, header background `#f8fafc`, alternating row shading `#fbfcfe`, font size 0.875rem, horizontal scroll wrapper.
   - Remove any legacy Mermaid container sizing hacks.
2. In `ui/static/app.js`:
   - Remove `renderMermaidDiagrams()` and all Mermaid execution calls.
   - Ensure `pre > code` renders clean monospace code blocks if code is returned, without attempting to parse as Mermaid.
3. In `ui/static/index.html`:
   - Remove `<script src="...mermaid.min.js">` script tag to reduce bundle size and prevent unhandled global errors.
```

### 3. Relevant Files & Dependencies
* Files: `ui/static/styles.css`, `ui/static/app.js`, `ui/static/index.html`
* Dependencies: None

### 4. Acceptance Criteria
* Markdown tables render with clean borders, header background, and responsive horizontal scrolling.
* Zero Mermaid script tags or render calls in frontend.
* Zero bomb icons (`.error-icon`, `#dmermaid*`) can ever appear on the page.

### 5. Human-Verifiable Steps
* Open `http://localhost:8000` in browser. Inspect Console: 0 Mermaid warnings/errors. Send a query that includes a table: table renders with `#f8fafc` header and clean borders.

---

## Step 4: Generic Agent Orchestrator & Free Gemini 2.0 Flash ReAct Engine

### 1. Description & Why
Refactor `agent/orchestrator.py` and `agent/providers.py` into a domain-agnostic ReAct tool-calling loop:
1. Generic/conversational queries answer directly (0 tool calls, immediate TTFT).
2. Textbook inquiries invoke `get_textbook_structure`, `get_relevant_chunks`, and `get_media_and_tables`.
3. LLM inspects semantic descriptions of media/tables and selects only relevant assets.
4. Pass raw LLM output through the **Visual Presentation Layer** (`agent/sanitizers.py`) to scrub stray math signs (`15$`, `35$`), balance bolding, and format sub/superscripts before streaming.

### 2. Self-Contained Prompt for Fresh Agent Session
```text
Task: Refactor `agent/orchestrator.py`, `agent/providers.py`, and `agent/sanitizers.py`.
1. In `agent/sanitizers.py`:
   - Add `_sanitize_universal_typography(text: str) -> str`:
     - Strips trailing dollars from numbers: `re.sub(r"(\d+)\$", r"\1", text)`.
     - Normalizes standard scientific/medical symbols: Na⁺, Mg²⁺, Ca²⁺, K⁺, β, ≥, ≤.
     - Auto-balances unclosed markdown tags (e.g. unclosed `**` at line endings).
2. In `agent/providers.py`:
   - Configure `gemini-2.0-flash` (or `gemini-1.5-flash`) via `google.genai` / `google.generativeai` with native function calling using `TOOL_DEFINITIONS`.
   - Pass tool results with semantic descriptions so the model selects relevant figures.
3. In `agent/orchestrator.py`:
   - Retire the `AttendingPlanner` dependency from `stream_turn()` and `run_turn()`.
   - If the user query is generic/conversational, stream direct response with 0 tool calls.
   - For textbook inquiries, execute tool loop, select relevant figures by description, apply `_sanitize_universal_typography`, and stream SSE tokens, citations, and figures.
```

### 3. Relevant Files & Dependencies
* Files: `agent/orchestrator.py`, `agent/providers.py`, `agent/sanitizers.py`
* Dependencies: `google-generativeai` / `google-genai`, `openai`

### 4. Acceptance Criteria
* Generic questions ("What is an easement?", "What is entropy?", "Hi") answer in 2-3 sentences with 0 tool calls.
* Textbook questions stream direct answer first, clean Markdown tables, and verified citations.
* Stray `$15`, `$35` and unclosed `**` are automatically removed.

### 5. Human-Verifiable Steps
* Test query `"What is an easement?"` via SSE endpoint → verifies 0 tool events, immediate response.
* Test query `"Contraindications of combined oral contraceptives"` → verifies table output, clean citations, no bomb icons.

---

## Step 5: Codebase Cleanup (Retire Medical Planners & Update Documentation)

### 1. Description & Why
Delete obsolete medical-only code and update legacy documentation to reflect the universal architecture.

### 2. Self-Contained Prompt for Fresh Agent Session
```text
Task: Clean up legacy medical-only code and update documentation.
1. Deprecate / remove `agent/planner.py` (`AttendingPlanner`).
2. Update `docs/architecture.md`, `docs/clinical-agent.md`, and `docs/api-reference.md` to reflect the Universal Textbook RAG Engine (multi-domain, tools on demand, visual presentation layer, zero synthetic flowcharts).
3. Ensure backward-compatibility aliases exist so existing tests don't break.
```

### 3. Relevant Files & Dependencies
* Files: `agent/planner.py`, `docs/architecture.md`, `docs/clinical-agent.md`, `docs/api-reference.md`

### 4. Acceptance Criteria
* No unused dead code or broken references.
* Documentation accurately reflects the generic V2 architecture.

### 5. Human-Verifiable Steps
* Grep for `AttendingPlanner` across codebase to confirm clean deprecation.

---

## Step 6: Universal E2E Test Suite Across All Books

### 1. Description & Why
Expand and verify integration test suite to cover all indexed books (Williams, Anatomy, Harrison, Cornea, and mock legal/general texts). Verify table-first rendering, generic direct answers, citation integrity, and diagram plate extraction.

### 2. Self-Contained Prompt for Fresh Agent Session
```text
Task: Author and run universal integration tests.
1. In `tests/integration/test_universal_rag.py`:
   - Test generic query: asserts 0 tool calls, direct reply.
   - Test table formatting: asserts response contains valid Markdown table syntax.
   - Test typography sanitizer: asserts no stray `$`, balanced `**`.
   - Test figure extraction across all indexed books: asserts valid thumbnail URLs and 0 page offset errors.
2. Run full pytest suite across unit and integration tests.
```

### 3. Relevant Files & Dependencies
* Files: `tests/integration/test_universal_rag.py`, `tests/integration/`
* Dependencies: `pytest`, `pytest-asyncio`, `httpx`

### 4. Acceptance Criteria
* 100% of integration and unit tests pass.
* Zero test regressions.

### 5. Human-Verifiable Steps
* Run `.\.venv\Scripts\python -m pytest tests/integration tests/unit -v` → 100% green.

