# Universal Textbook Agent & Reasoning Engine: Architecture Guide

This document details the reasoning, planning, retrieval routing, and streaming architecture of the **CliniSource Universal Textbook Agent**.

---

## 1. Universal Reasoning Philosophy

General-purpose conversational AI models frequently stumble in specialized textbook question-answering because they jump directly to generating prose before structuring their search or verifying ground truth against authoritative reference canon.

In CliniSource, the agent functions as a **Universal Textbook Intelligence Engine** across multiple domains (Medicine, Law, Engineering, Science):
1. **Direct Answer First**: Resolves the user's inquiry directly in the first 1–2 sentences without unnecessary monograph preamble.
2. **Reference On-Demand**: Generic questions (e.g., greetings, conceptual definitions) are answered immediately with zero tool latency. Textbook search tools are invoked dynamically when statutory, scientific, or clinical evidence is needed.
3. **Structured Tables for Data & Decision Logic**: Replaces fragile synthetic flowcharts with clean, accessible Markdown tables for comparisons, criteria, and multi-step decision workflows.
4. **Visual Presentation Layer**: Cleans up math/LaTeX artifacts, standardizes Unicode symbols, auto-balances markdown, and binds citations interactively.

---

## 2. Agent Architecture Overview

```
                                  USER QUERY
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │   LLM (Gemini 2.0 Flash)  │ (Free Tier ReAct Engine)
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

### 1. Invariant System Prompt & Context Caching
Located in `agent/prompts.py`, `INVARIANT_SYSTEM_PROMPT` contains the universal persona, citation integrity rules, and table-first formatting guidelines.
- **Prompt Caching Integration**: By keeping the system prompt static and placed as an immutable prefix, Google Gemini's **Context Caching** caches the prompt tokens on Google's servers. Subsequent turns reuse the cached context, reducing Time-to-First-Token (TTFT) by up to 60–80%.

### 2. Universal Tools (`agent/tools_spec.py`)
- `get_textbook_structure`: Returns hierarchical outlines (Titles, Chapters, Sections) matching query terms.
- `get_relevant_chunks`: Retrieves granular passages and text blocks with 1-based citation IDs.
- `get_media_and_tables`: Surfaces authentic figures, diagram plates, and tables along with their semantic descriptions.

### 3. Visual Presentation Layer (`agent/sanitizers.py`)
- Sanitizes raw LaTeX tags, strips trailing dollar signs from numbers (`15$`, `35$`), normalizes ion and mathematical typography (`Na⁺/K⁺-ATPase`, `Mg²⁺`, `≥`, `≤`), and auto-balances bold markers.

### 4. Interactive Citations & Evidence Drawer
- Every claim cited as `[1]`, `[2]` is parsed into interactive citation pills in the UI. Clicking a pill smoothly slides open the **Evidence Drawer**, showing the exact source textbook title, chapter hierarchy, physical and printed page numbers, and verified excerpt.
