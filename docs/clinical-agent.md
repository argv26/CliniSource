# CliniSource: Agent Reasoning & Presentation Engine

This document details the reasoning, planning, retrieval routing, streaming, and formatting architecture of the **CliniSource Agent Engine**.

---

## 1. Universal Reasoning Philosophy

General-purpose conversational AI models frequently stumble in specialized textbook question-answering because they jump directly to generating prose before structuring their search or verifying ground truth against authoritative reference canon.

In CliniSource, the agent functions as a **Universal Textbook Intelligence Engine** across multiple disciplines (Medicine, Law, Engineering, Science, and Academia):

1. **Direct Answer First**: Resolves the user's inquiry directly in the first 1–2 sentences without unnecessary monograph preamble or forced tool retrieval.
2. **Reference On-Demand**: Generic questions (e.g., greetings, conceptual definitions) are answered immediately with zero tool latency. Specialized textbook search tools are invoked dynamically when statutory, scientific, or clinical evidence is needed.
3. **Structured Tables for Data & Decision Logic**: Replaces fragile synthetic flowcharts with clean, accessible Markdown tables for comparisons, criteria, and multi-step decision workflows.
4. **Visual Presentation Layer**: Cleans up math/LaTeX artifacts, standardizes Unicode symbols, auto-balances Markdown, and binds citations interactively to verified textbook pages.

---

## 2. Agent Workflow Architecture

```
                              USER QUERY
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │   LLM (Gemini 2.0 Flash)  │ (High-Speed ReAct Engine)
                    └─────────────┬─────────────┘
                                  │
           ┌──────────────────────┴──────────────────────┐
           ▼                                             ▼
  [Generic / Conversational]                   [Textbook Reference Needed]
  • "What is an easement?"                    • Law / Medicine / Engineering
  • "Explain entropy simply"                  • Specific sections, rules, cutoffs
           │                                             │
  Direct Answer First                         Calls Tools on Demand:
  (0 search latency,                                     │
   0 tool calls)                                         ▼
                                            1. get_textbook_structure(keywords)
                                               → Returns Chapter / TOC Outline
                                                 │
                                                 ▼
                                            2. get_relevant_chunks(query, section_id)
                                               → Fetches specific text passages
                                                 │
                                                 ▼
                                            3. get_media_and_tables(query, section_id)
                                               → Returns diagrams & tables with
                                                 captions & descriptions
                                                 │
                                                 ▼
                                            LLM inspects descriptions & selects
                                            ONLY relevant media to cite/display
                                                 │
                                                 ▼
                    ┌───────────────────────────┐
                    │   FINAL RUNTIME PHASE:    │
                    │ Visual Presentation Layer │
                    └─────────────┬─────────────┘
                                  │
                 • Pristine Markdown tables for data/logic
                 • Authentic textbook diagram plates
                 • Strips stray math/LaTeX ($15, 35$)
                 • Binds citations [1] to Evidence Drawer
                                  │
                                  ▼
                           SSE Stream to UI
```

---

## 3. Core Engine Components

### 1. Invariant System Prompt & Context Caching (`agent/prompts.py`)
`INVARIANT_SYSTEM_PROMPT` contains the universal persona, citation integrity rules, and table-first formatting guidelines:
- **Prompt Caching Integration**: By keeping the system prompt static and placed as an immutable prefix, Google Gemini's **Context Caching** caches the prompt tokens on Google's servers. Subsequent turns reuse the cached context, reducing Time-to-First-Token (TTFT) by up to 60–80%.
- **Table-First Mandate**: The prompt strictly instructs the LLM to represent sequential and comparative logic in Markdown tables or numbered decision steps ($1 \rightarrow 2 \rightarrow 3$), forbidding synthetic Mermaid syntax.

### 2. Universal 3-Tool Suite (`agent/tools_spec.py`)
- `get_textbook_structure(keywords, book_slug)`: Returns hierarchical outlines (Titles, Chapters, Sections) matching query terms.
- `get_relevant_chunks(query, book_slug, section_id, limit)`: Retrieves granular passages and text blocks with 1-based citation IDs.
- `get_media_and_tables(query, book_slug, section_id)`: Surfaces authentic figures, diagram plates, and tables along with their semantic descriptions.

### 3. Visual Presentation Layer (`agent/sanitizers.py`)
- Post-processes all token deltas and complete responses.
- Sanitizes raw LaTeX tags, strips trailing dollar signs from numbers (`15$`, `35$`), normalizes ion and mathematical typography (`Na⁺/K⁺-ATPase`, `Mg²⁺`, `T₄`, `TRβ₂`, `≥`, `≤`), and auto-balances bold markers.
- Converts textbook bibliography citations into non-colliding `(Ref X)` text so only real, verified textbook passages become clickable interactive citation pills.

### 4. Interactive Citations & Evidence Drawer (`context/citations.py`)
- Every claim cited as `[1]`, `[2]` is parsed into interactive citation pills in the UI.
- Clicking a pill smoothly slides open the **Evidence Drawer**, showing the exact source textbook title, chapter hierarchy, physical and printed page numbers, and verified excerpt.

### 5. Multi-Turn Context Management (`context/manager.py`)
- Manages multi-turn conversation windows, preserving recent context while virtualizing earlier turns to stay strictly within token budgets.
- Persists session turns in SQLite WAL mode with auto-titling after the initial exchange.

### 6. Multi-Provider & Local Offline Fallback (`agent/offline.py`)
- Primary provider: Google Gemini 2.0 Flash with native tool-calling.
- Secondary provider: OpenAI GPT-4o / GPT-4o-mini tool-calling loop.
- Offline provider: Local smart synthesizer (`agent/offline.py`) that executes BM25 retrieval directly and formats verified textbook passages with zero external API dependencies.
