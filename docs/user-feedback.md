# CliniSource: User Experience & Clinical Feedback Solutions

This document consolidates clinical user feedback, usability observations, and physician requirements gathered across testing sessions and deployment releases, presented alongside the architectural solutions implemented to address them.

---

## 1. Executive Summary: Feedback & Engineering Solutions

| # | User Voice & Clinical Requirement | Root Engineering Challenge | Architectural Solution Implemented | Verification Status |
|---|---|---|---|---|
| **1** | *"There is no past chat history on the left side; I lose my case when I refresh."* | Stateless browser sessions lose conversation context on page reload. | Multi-turn SQLite session database (`app_users.db`) with auto-titling, session switching, and cascade deletion. | **Verified & Active** |
| **2** | *"I can't remove or hide textbooks; I only want Endocrinology, not Anatomy."* | Monolithic search indices query all books without user scope control. | Dedicated Library Manager and personal "My Study Library" with 1-click active toggles and strict user selection sovereignty. | **Verified & Active** |
| **3** | *"When a question is generating, the input freezes and I can't stop or interrupt it."* | Backend generation was uninterruptible, locking client UI until full turn completed. | `AbortController` frontend button and backend SSE stream cancellation on client disconnect. | **Verified & Active** |
| **4** | *"Answers are text-only; we need medical diagrams, anatomic plates, and pathways."* | Dense prose without visual context degrades clinical learning and clarity. | PyMuPDF column-aware diagram plate cropping, Object Storage cache, and responsive slider carousel. | **Verified & Active** |
| **5** | *"Generation takes too long; I'm staring at a spinning loader for 15 seconds."* | Uncached prompts and unnecessary tool round-trips cause high Time-to-First-Token. | Invariant prompt caching prefix + Direct Answer First (0 tool latency for broad queries) + zero-multimodal LLM inference. | **Verified & Active** |
| **6** | *"The Evidence Drawer displays internal developer database IDs and bibliography lists."* | Internal database keys and end-of-chapter reference lists polluted clinical evidence. | Structural breadcrumbs (`Part > Chapter > Section`), bibliography chunk filters, and physical-to-print page calibration. | **Verified & Active** |
| **7** | *"Citation bracket numbers like [14] in text don't open or lead to 404 errors."* | Publisher bibliography citations (`[14]`) collided with application citation pills (`[1]`). | Citation normalizer converts bibliography numbers to `(Ref 14)` so only real verified citations are clickable. | **Verified & Active** |
| **8** | *"The sidebar squashes everything on laptop screens; book list and chat list fight for space."* | Dual vertical lists in single container competed for screen space. | Independent dual-scroll containers (`overflow-y: auto`) with dynamic "Active Scope" counter pills and mobile drawer overlays. | **Verified & Active** |
| **9** | *"Formulas look broken with dollar signs and raw LaTeX tags like \text{...}."* | Raw typesetting math delimiters render unpredictably in web Markdown. | Post-processing typography sanitizer converts hormone symbols (`T₄`, `TRβ₂`) and ion formulas (`Na⁺/K⁺-ATPase`) to clean Unicode. | **Verified & Active** |
| **10** | *"I want to upload my own textbook PDF without asking an administrator or restarting the server."* | Ingestion previously required offline CLI execution and restart. | Web UI Drag-and-Drop upload modal with non-blocking background worker, TOC extraction, and live progress bar. | **Verified & Active** |
| **11** | *"System needs gold-standard internal medicine depth beyond basic anatomy."* | General clinical decision support requires comprehensive multi-specialty canon. | Indexed complete 4,273-page *Harrison's Principles of Internal Medicine (22nd Edition, 2025)* and 2,319-page *Williams Endocrinology (15th Edition)*. | **Verified & Active** |

---

## 2. Detailed Breakdown of Feedback & Architectural Solutions

### 1. Multi-Turn Session Persistence & Auto-Titling
- **User Voice**: *"There is no past chat history on the left side; I lose my case when I refresh."*
- **Clinical Need**: Clinicians research multiple patient presentations or study topics in parallel and require continuous access to past consultations.
- **Architectural Solution**:
  - Implemented `ui/sessions.py` backed by SQLite in Write-Ahead Logging (WAL) mode.
  - Added session switching in the sidebar with live turn counts and timestamps.
  - Built intelligent auto-titling: after the first question-answer exchange, the system generates a concise title (e.g., *"Adrenal Cortex Zonation"* instead of generic *"New Consultation"*).
  - Added cascade deletion so users can cleanly remove past cases.

---

### 2. User Selection Sovereignty & Scope Control
- **User Voice**: *"Target textbook is nice, but I don't want anatomy book — I only want endocrinology."*
- **Clinical Need**: A clinician preparing for specialized rounds needs focused reference material without extraneous basic science passages diluting search results.
- **Architectural Solution**:
  - Established a clean separation between **Global Catalog** (all volumes indexed on the server) and **My Study Library** (user-curated active collection).
  - Implemented a dedicated **Library Manager** (`#view-library`) with search, specialty filtering, and 1-click addition/removal.
  - Enforced **User Selection Sovereignty**: the retrieval engine strictly queries only the books selected by the user.

---

### 3. Immediate Generation Cancellation (Stop Generation)
- **User Voice**: *"When one question is loading, I can't click enter or interrupt it (add a stop button)."*
- **Clinical Need**: Users who submit typos or reframe their question need to immediately halt generation without waiting for full completion.
- **Architectural Solution**:
  - Added an interactive **Stop Generation** button in the chat interface wired to `AbortController`.
  - Configured FastAPI SSE streaming generator to listen for client disconnects and instantly cancel background agent tasks, conserving LLM tokens and thread capacity.

---

### 4. Authentic Visual Diagram Plates & Responsive Carousel
- **User Voice**: *"Nice but no diagram (fetch related diagrams if necessary)."*
- **Clinical Need**: Medical pathways, surgical anatomy, and diagnostic decision algorithms require visual diagrams alongside text.
- **Architectural Solution**:
  - Built an automated column-aware figure resolution engine in `ui/diagrams.py`: detects diagram captions, isolates column gutters to prevent text bleed, and crops crisp 180 DPI plates.
  - Emits figure cards early over SSE so diagrams appear smoothly before LLM text synthesis concludes.
  - Serves cropped images directly from storage, avoiding multimodal vision token costs and latency.
  - Added a responsive sliding carousel with touch chevrons and modal expander for detailed inspection.

---

### 5. Response Speed & Time-to-First-Token
- **User Voice**: Long wait times during generation; need for faster answers.
- **Clinical Need**: Bedside consultations require answers in seconds, not tens of seconds.
- **Architectural Solution**:
  - **Direct Answer First**: Answers general and conceptual queries immediately with 0 tool latency.
  - **Invariant Prompt Caching**: System prompt and persona are placed as an immutable prefix, enabling Gemini Context Caching to cut TTFT by up to 60–80%.
  - **FTS5 BM25 Retrieval**: Sub-30ms full-text keyword retrieval across 34,000+ chunks.

---

### 6. Clean Citations & Interactive Evidence Drawer
- **User Voice**: *"What is Section ID? Is the page number even correct?"*
- **Clinical Need**: Citations must be verifiable against physical book copies without exposing internal database keys.
- **Architectural Solution**:
  - Removed internal database IDs from the interface; replaced with clean breadcrumbs (`Part > Chapter > Section`).
  - Calibrated physical PDF coordinates against printed textbook pagination to guarantee exact page numbers.
  - Filtered end-of-chapter bibliographies from chunking so only primary clinical evidence is cited.
  - Interactive citation pills (`[1]`, `[2]`) open the slide-out **Evidence Drawer** showing the verified excerpt and page bounds.

---

### 7. Medical Typography & Formatting Normalization
- **User Voice**: Text had ugly dollar signs around hormones (`$T4$`, `$TR\beta2$`) and random bibliography numbers like `[14]` that looked like broken buttons.
- **Clinical Need**: Clear medical communication without typesetting artifacts or broken links.
- **Architectural Solution**:
  - Implemented `agent/sanitizers.py` to post-process all responses:
    - Normalizes LaTeX math tags into clean Unicode text (e.g., `T₄`, `TRβ₂`, `Na⁺/K⁺-ATPase`).
    - Decouples textbook bibliography citations into plaintext `(Ref 14)` so only real verified citations become interactive badges.
    - Resolves hyphenated line breaks (`hy- \n perthyroidism` &rarr; `hyperthyroidism`).
    - Standardizes mathematical operators (`≥`, `≤`).

---

### 8. Multi-Volume Scale & Production Concurrency
- **User Voice**: The system needed to support full-length medical masterworks and handle multiple concurrent users reliably.
- **Clinical Need**: Robustness under real clinical load.
- **Architectural Solution**:
  - Configured SQLite with **Write-Ahead Logging (WAL mode)** for concurrent non-blocking reads during active background writes.
  - Thread-locked rate limiter using SQLite `BEGIN IMMEDIATE;` transactions prevents race conditions under burst traffic.
  - Successfully indexed and validated over 34,000 chunks across 9,200+ pages of reference canon.
