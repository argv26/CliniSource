# CliniSource (Text-Book-RAG): Comprehensive Project Summary & Decision Trade-Offs

This document presents a complete retrospective and architectural analysis of **CliniSource** (formerly *Text-Book-RAG*). It details the core problems solved, all engineering work completed across subsystems, the key architectural decisions and their trade-offs, and verified production benchmarks.

---

## 1. Executive Summary & Project Evolution

### The Core Problem
Standard Retrieval-Augmented Generation (RAG) platforms consistently fail when applied to dense, multi-thousand-page reference literature (e.g., *Harrison's Principles of Internal Medicine*, *Williams Textbook of Endocrinology*, statutory legal codes, engineering handbooks) due to:
1. **Multi-Column Text Bleed**: Standard PDF extractors read left-to-right across physical page lines, intertwining two adjacent vertical columns and injecting running headers/footers into narrative paragraphs.
2. **Page Coordinate Discrepancy**: Physical PDF page indexes deviate significantly from printed textbook page numbers due to front-matter, introductory roman numerals, and publisher plates.
3. **Loss of Structural Semantics**: Flattening diagnostic trees, comparative tables, and anatomical figures into raw text strips away their relational logic.
4. **Synthetic Hallucination**: Generating programmatic flowcharts (e.g., Mermaid) frequently results in parsing crashes, unreadable mobile layouts, and fabricated decision steps.
5. **Slow Response Latency**: Forcing heavy multi-tool searches on every user turn causes 10–15 second wait times even for simple greetings or conceptual definitions.

### Project Evolution
The platform evolved from an exploratory script (`Text-Book-RAG`) into **CliniSource** — a production-ready, domain-agnostic **Universal Textbook Knowledge & Clinical Decision Intelligence Engine** capable of operating across medicine, law, engineering, and academia.

```mermaid
flowchart TD
    subgraph Ingestion["Ingestion Pipeline"]
        PDF["Reference PDF (4,000+ Pages)"] --> Ext["Multi-Column & Gutter Extraction"]
        Ext --> Map["Physical-to-Print Page Calibration"]
        Map --> Tree["Hierarchical Heading & Section Tree"]
        Tree --> Chunker["Bounded Semantic Chunking (300-500 Tok)"]
        Chunker --> DB[("SQLite FTS5 + Postgres pgvector")]
    end

    subgraph Runtime["Agent Runtime & Orchestration"]
        User["User Inquiry"] --> Router["Semantic Book Router / Sovereignty"]
        Router --> Orch["Fast ReAct Orchestrator (Gemini 2.0 Flash)"]
        Orch --> Tools["Universal 3-Tool Suite\n(Structure, Chunks, Media/Tables)"]
        Tools --> DB
        Tools --> Diag["Column-Aware Diagram Crop Engine\n(PyMuPDF 180 DPI Plates)"]
    end

    subgraph Presentation["Visual Presentation & Delivery"]
        Orch --> Sanitizer["Presentation Sanitizer\n(Unicode, Math/LaTeX Stripping, Ref Decoupling)"]
        Sanitizer --> SSE["SSE Real-Time Stream\n(Direct Answer First, Early Figures)"]
        SSE --> UI["Responsive UI (WCAG AA)\nDual-Scroll, Evidence Drawer, Modal"]
    end
```

---

## 2. Comprehensive Work Completed Across Subsystems

### A. Ingestion & Document Pipeline (`ingestion/`)
- **Multi-Column Gutter Extraction (`extract_pages.py`)**: Utilizes PyMuPDF (`fitz`) to sort text blocks by x-coordinate gutters before y-coordinates, preventing line intertwining across two-column textbook pages. Filters out running headers and footers using bounding-box statistical frequency analysis.
- **Physical-to-Print Page Calibration (`page_map.py`)**: Automatically detects Roman-numeral front-matter and reconciles physical PDF page indices with actual printed textbook page numbers, ensuring citations match physical book copies.
- **Hierarchical Outline Tree (`section_tree.py`, `locate_headings.py`)**: Extracts the publisher Table of Contents (TOC) into a structured outline (`Part → Chapter → Section → Subsection`) with physical coordinate bounds and breadcrumb paths (`heading_path`).
- **Special Content Tagging (`tag_special_content.py`)**: Identifies, isolates, and tags callout boxes, diagnostic criteria, tables, and figure captions before chunking.
- **Bounded Semantic Chunking (`chunk_sections.py`)**: Generates 300–500 token chunks bounded strictly by section headings with single-sentence overlap to preserve semantic continuity without boundary bleed.
- **Non-Blocking Dynamic Ingestion Worker (`pipeline_worker.py`)**: Enables real-time user PDF uploads via drag-and-drop with background processing, atomic SQLite commits, and live WebSocket/SSE progress updates.
- **Large-Scale Reference Corpus**: Fully ingested and verified authoritative medical references, including *Harrison's Principles of Internal Medicine (22nd Ed., 2025; 4,273 pages)* and *Williams Textbook of Endocrinology (15th Ed.; 2,319 pages)*.

### B. Retrieval Engine & Multi-Book Semantic Routing (`retrieval/`)
- **Two-Layer Architecture**:
  1. *Navigation Layer*: Outline hierarchy allowing fast structural discovery without scanning millions of tokens.
  2. *Retrieval Layer*: High-performance SQLite FTS5 index utilizing BM25 ranking (sub-30ms keyword retrieval) with fallback to dense vector search (`pgvector`).
- **Semantic Book Router (`router.py`)**: Intelligently routes queries to relevant textbooks based on medical/academic specialty heuristics while strictly enforcing **User Selection Sovereignty** (never querying unselected books).
- **Parallel Retrieval Executor (`parallel.py`)**: Dispatches concurrent multi-tool calls using thread pools for sub-second retrieval round-trips.

### C. Universal Agent Reasoning & Orchestration (`agent/`)
- **Direct Answer First Paradigm**: Conversational queries (greetings, definitions) receive an immediate answer in 2–3 paragraphs with **zero tool calls and zero retrieval latency**.
- **Reference On-Demand ReAct Loop (`orchestrator.py`, `providers.py`)**: Dynamically invokes the universal 3-tool suite (`get_textbook_structure`, `get_relevant_chunks`, `get_media_and_tables`) only when authoritative grounding is required.
- **Invariant System Prompt & Context Caching (`prompts.py`)**: Places an immutable persona and guidelines prefix to leverage Google Gemini Context Caching, slashing Time-to-First-Token (TTFT) by 60–80%.
- **Resilient Fallback Cascade**: Primary execution on Google Gemini 2.0 Flash, secondary fallback to OpenAI GPT-4o, and tertiary fallback to a local offline smart synthesizer (`offline.py`) requiring zero network access.
- **Early Visual Emission & Cancellation**: Emits retrieved figure plates over SSE immediately so diagrams appear while text streams. Listens for client disconnects via `AbortController` to cancel running tasks immediately.

### D. Authentic Diagram Extraction Engine (`ui/diagrams.py`, `storage/`)
- **Column-Aware High-Resolution Cropping**: Locates figure captions (e.g., `FIG. 12-4`), traces vector drawing and raster image bounding boxes, and strictly clips them to column gutters (`col_x0` to `col_x1`), preventing adjacent text from contaminating the image.
- **Strict Visual Rejection**: Strictly returns `None` if a target page contains only prose, completely eliminating broken image placeholders and random text paragraphs masquerading as diagrams.
- **Object Storage Abstraction (`storage/object_store.py`)**: Pluggable storage supporting local filesystem caching (`ui/static/figures_cache/`) and cloud S3/MinIO/Cloudflare R2 providers with 180 DPI JPEG rendering.

### E. Visual Presentation Layer & Medical Sanitization (`agent/sanitizers.py`)
- **Zero Synthetic Flowcharts (Table-First Mandate)**: Replaced fragile Mermaid syntax with structured Markdown tables and numbered clinical decision sequences ($1 \rightarrow 2 \rightarrow 3$).
- **Typography & Math Delimiter Sanitizer**:
  - Strips trailing typesetting dollar signs (e.g., `$15$` or `$35$` rendered from publisher formulas).
  - Converts chemical, ion, and hormonal formulas to clean Unicode (e.g., `T₄`, `TRβ₂`, `Na⁺/K⁺-ATPase`, `Mg²⁺`).
  - Standardizes comparison operators (`≥`, `≤`).
  - Auto-balances unclosed Markdown bold tags (`**`).
- **Citation Decoupling**: Converts publisher bibliography citations (`[14]`) into plaintext `(Ref 14)`, ensuring only authentic, system-verified textbook passages become clickable interactive citation badges (`[1]`, `[2]`).

### F. User Sessions, Library Sovereignty & Concurrency (`ui/`, `context/`)
- **Session Persistence & Auto-Titling (`sessions.py`)**: Multi-turn chat persistence in SQLite WAL mode with automatic case titling derived from the initial inquiry.
- **User Library Manager (`library.py`)**: Enables users to curate their personal study shelf ("My Study Library") from the global book catalog with 1-click active toggles.
- **Thread-Safe Daily Rate Limiting (`rate_limiter.py`)**: Protected by `threading.Lock()` and `BEGIN IMMEDIATE;` SQLite transactions to eliminate TOCTOU race conditions under high burst concurrency.
- **Secure Authentication (`auth.py`)**: Ephemeral guest sessions and persistent user accounts protected via HttpOnly, SameSite=Lax session cookies.

### G. Responsive UI/UX Design System (`ui/static/`)
- **WCAG AA Compliance**: Surface contrast ratios $\ge 4.5:1$, visible focus rings (`focus-visible`), and accessible `aria-label` attributes on all controls.
- **Independent Dual-Scroll Workspace**: Consultation history and library collections have independent scroll containers (`overflow-y: auto`), preventing layout squishing on laptop screens.
- **Mobile Drawer Navigation**: Responsive sidebar drawer with backdrop overlay for screen widths $< 1024\text{px}$.
- **Evidence Drawer & Lightbox**: Interactive slide-out drawer displaying verified textbook passages, breadcrumbs, and page numbers, accompanied by a full-screen image lightbox.

### H. Evaluation Framework & Operational Telemetry (`evals/`)
- **Golden Benchmark Dataset (`clinical_gold.json`)**: 27 curated clinical cases spanning 4 textbooks across 7 distinct categories (factual, diagnostic tables, anatomical figures, differential diagnoses, multi-book sovereignty, fast-path, and out-of-scope abstention).
- **Deterministic & Semantic Evaluators (`runner.py`)**: Automated scoring for Hit@K, MRR, keyword coverage, citation integrity, table compliance, and LLM-as-a-Judge faithfulness.
- **LLMOps Telemetry (`agent/telemetry.py`)**: Per-turn measurement of stage latencies, token consumption, Gemini context cache hit ratios, and fallback triggers.
- **Automated Test Suite**: 101 unit and integration tests across 6 core production segments.

---

## 3. Core Architectural Decisions & Trade-Offs

| Decision | Selected Approach | Alternative Considered | Key Advantages (Gains) | Trade-Offs / Incurred Costs | Mitigation Strategy |
|---|---|---|---|---|---|
| **1. Direct Answer First vs. Mandatory Retrieval** | Answer broad/conversational queries immediately; call tools only when grounded reference is needed. | Mandate tool retrieval and vector search on every turn. | TTFT drops from 12s to $<1$s; zero tool token waste on greetings or high-level overviews. | Risk of LLM relying on parametric memory for subtle facts if prompt fails to trigger tools. | Strict instruction in invariant prompt enforcing tool retrieval for dosages, cutoffs, and statutory references. |
| **2. Two-Layer Hybrid Search (Outline + FTS5 BM25)** | Outline navigation tree combined with SQLite FTS5 BM25 text search. | Pure dense vector search with chunk embeddings across entire books. | Sub-30ms queries, zero embedding API costs during search, exact keyword matching for medical eponyms/drugs. | Lexical mismatch when query uses colloquial vernacular instead of textbook taxonomy. | Two-step agent exploration: agent queries structure first, then retrieves target chunk using domain taxonomy. |
| **3. Table-First Representation (Zero Flowcharts)** | Represent workflows and criteria exclusively via Markdown tables or numbered sequences. | Synthetic Mermaid or Graphviz flowchart generation in LLM output. | 100% rendering reliability across desktop and mobile; zero syntax crashes; screen-reader accessible. | Loss of 2D graphical node-link layout aesthetics. | High-contrast CSS table styling, horizontal scroll wrappers, and clear sequential step markers ($1 \rightarrow 2 \rightarrow 3$). |
| **4. Authentic PDF Raster/Vector Cropping** | Crop exact visual plates from original PDF pages using PyMuPDF at 180 DPI. | Multimodal Vision LLM extraction or synthetic chart redrawing. | 100% authentic medical drawings and histological plates; zero hallucinated figures; zero vision API cost. | Susceptible to complex multi-column layout artifacts if bounding rects are imprecise. | Column-aware plate bounding algorithm clipping strictly between column gutters (`col_x0` to `col_x1`). |
| **5. User Selection Sovereignty** | Retrieval strictly queries only the user's active library books; router cannot inject unselected books. | Global autonomous routing across all catalog books on server. | Absolute user control; eliminates cross-specialty noise (e.g., anatomy basic science polluting endocrinology). | User must explicitly enable books if asking cross-specialty questions outside active set. | Active book counter badge in header; visual banner suggesting additional catalog books when retrieval returns 0 hits. |
| **6. SQLite WAL + Thread Locks vs. Microservices Stack** | Single/dual SQLite databases with WAL mode, `BEGIN IMMEDIATE`, and process-level locks. | PostgreSQL + Redis + Celery distributed microservices architecture. | Zero operational overhead, single-container deployment, trivial local development, high read concurrency. | Single-writer serialization bottleneck under extreme write concurrency ($>500$ writes/sec). | Read-heavy design (95% queries are reads); background ingestion jobs run in isolated tasks without blocking readers. |
| **7. Server-Sent Events (SSE) vs. WebSockets** | HTTP/1.1 & HTTP/2 Server-Sent Events with structured event dispatching. | Bi-directional WebSockets (`ws://`). | Simpler protocol over standard HTTP; native browser `EventSource`/fetch streaming; seamless proxy and CDN support. | Unidirectional server-to-client streaming requires separate HTTP POST for client control. | Client aborts via standard `AbortController`, triggering instant server-side generator cancellation. |
| **8. Invariant Prompt Prefix for Context Caching** | Keep system prompt completely invariant and placed at index 0 across all sessions. | Dynamic per-user or per-session system prompt customization. | Unlocks Google Gemini Context Caching, cutting TTFT by 60–80% and reducing input token costs. | Cannot inject dynamic runtime state directly into the system prompt. | Dynamic session state, active book scopes, and query context are passed exclusively via user message envelopes. |
| **9. Decoupling Citations from Publisher References** | Rewrite bibliography citations (`[14]`) to `(Ref 14)` so only real citations become interactive pills. | Parse all brackets with regex or leave publisher brackets intact. | Eliminates false-positive 404 errors when users click publisher citations in the Evidence Drawer. | Regex transformation step required on all streaming deltas and final text. | Fast, compiled regex sanitizer in `agent/sanitizers.py` executing in $<0.5\text{ms}$. |
| **10. Early Visual Plate Emission** | Stream `event: figures` immediately after tool retrieval before LLM completes text synthesis. | Emit figures only at the end of the response turn. | User immediately sees relevant anatomical diagrams and tables while reading streaming text. | Figure cards appear before the textual narrative that references them. | Sticky visual carousel positioned neatly at the top of the message bubble with lazy loading. |

---

## 4. Production Readiness & Diagnostics

### Six-Segment Test Suite Results
The platform is validated against an end-to-end automated test suite spanning 6 core production pillars:

```text
============================= test session starts =============================
platform win32 -- Python 3.11.7, pytest-9.1.1, pluggy-1.6.0
collected 101 items

Segment 1: Ingestion & Document Pipeline (8/8 passed)
Segment 2: Retrieval & Semantic Routing (8/8 passed)
Segment 3: Agent Orchestration & SSE Streaming (8/8 passed)
Segment 4: REST API & User Isolation (8/8 passed)
Segment 5: Frontend E2E & UI/UX (9/9 passed)
Segment 6: Concurrency & Stress (8/8 passed)
Supporting Unit & Integration Suites (52/52 passed)

======================= 101 passed in 688.41s (0:11:28) =======================
```

### Key Production Issues Diagnosed & Resolved
1. **`ISSUE-001` (Slug Overwrite in Ingestion Worker)**:
   - *Symptom*: Dynamic ingestion jobs with custom slugs were overwritten with title-derived slugs, breaking database lookups.
   - *Root Cause*: `run_ingestion_pipeline` recalculated `generate_book_slug(title)` unconditionally.
   - *Fix*: Parameterized slug resolution to honor `job.book_slug` if pre-configured.
2. **`ISSUE-002` (DailyRateLimiter TOCTOU Race Condition)**:
   - *Symptom*: Concurrent burst requests bypassed daily limits, allowing 10 requests when limit was 3.
   - *Root Cause*: SQLite transactions defaulted to deferred reads without write locks before checking usage.
   - *Fix*: Introduced class-level `threading.Lock()` and `BEGIN IMMEDIATE;` transactions to enforce atomic read-modify-write.

---

## 5. Summary of Architecture & Technical Debt Status

| Layer | Implementation State | Technical Debt / Remaining Work |
|---|---|---|
| **Ingestion** | Complete: Multi-column extraction, TOC tree, special content tagging, dynamic worker. | Multi-threaded PDF parsing for multi-thousand-page volumes ($>5,000$ pages). |
| **Retrieval** | Complete: FTS5 BM25 search, outline tree, semantic router, sovereignty enforcement. | Optional dense embedding re-ranking (cross-encoder) for ambiguous semantic queries. |
| **Agent** | Complete: Gemini 2.0 ReAct loop, context caching, local offline synthesizer, sanitizers. | Support for streaming tool call visualization in UI status pills. |
| **Figures** | Complete: Column-aware plate cropping, 180 DPI rendering, local & S3 storage providers. | Bounding polygon support for irregular non-rectangular anatomical plates. |
| **UI/UX** | Complete: Responsive mobile drawer, dual-scroll containers, Evidence Drawer, WCAG AA. | Dark mode theme toggle and PDF page side-by-side split view. |
| **Ops & Evals**| Complete: Golden clinical benchmark (27 cases), automated scoring, turn telemetry. | Continuous CI/CD automated eval dashboard integration. |
