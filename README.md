---
title: CliniSource
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
---

# CliniSource

### *Universal Textbook Knowledge & Clinical Decision Intelligence Engine*

[![Tests](https://img.shields.io/badge/tests-101%20passed-success)](tests/)
[![Architecture](https://img.shields.io/badge/architecture-structure--aware-blue)](docs/architecture.md)
[![Clinical Reasoning](https://img.shields.io/badge/reasoning-universal--react-indigo)](docs/clinical-agent.md)
[![Live Demo](https://img.shields.io/badge/live--demo-render-emerald)](https://text-book-rag-etiz.onrender.com)
[![License](https://img.shields.io/badge/license-clinical--research-slate)](LICENSE)

CliniSource is an enterprise-grade clinical decision intelligence and universal textbook knowledge platform that arms clinicians, residents, researchers, and students with the verified canon of human medicine and academic literature in under 500 milliseconds.

> 🚀 **Live Production Deployment**: [https://text-book-rag-etiz.onrender.com](https://text-book-rag-etiz.onrender.com)  
> 🏗️ **System Architecture**: [docs/architecture.md](docs/architecture.md) | 🩺 **Agent Reasoning Guide**: [docs/clinical-agent.md](docs/clinical-agent.md)

---

## The Core Challenge

Modern reference systems and generative AI face an unsustainable trilemma:

1. **The Hallucination Hazard**: Generalist LLMs generate fluent, confident text that often fabricates drug dosages, cites nonexistent clinical trials, or conflates conflicting specialty guidelines. In clinical medicine and statutory disciplines, "probably correct" is a safety violation.
2. **The 15-Minute "Scrolling Tax"**: Incumbent reference tools and monolithic PDFs are exhaustive but slow. Clinicians and researchers must manually scroll through multi-thousand-page volumes to pinpoint a single titration guideline, contraindication, or statute while time runs short.
3. **The Geometric Failure of Generic RAG**: Reference textbooks are architecturally complex—relying on two-column gutters, diagnostic decision trees, cross-tabulated dosages, and anatomical figures. Standard vector chunkers flatten tables into unintelligible text, mangle reading gutters, lose printed pagination, and strip crucial diagnostic diagrams.

---

## The CliniSource Architecture

CliniSource bridges the gap between gold-standard authoritative reference canon (*Harrison's Principles of Internal Medicine*, *Williams Textbook of Endocrinology*, *Robbins Pathology*) and instant bedside decision support:

* **Direct Answer First & Reference On-Demand**: Answers generic and conceptual queries immediately in 2–3 concise paragraphs with **zero search latency and zero tool overhead**. Dynamically invokes textbook retrieval tools when statutory, scientific, or clinical proof is required.
* **3 Universal Tools**: Equipped with a domain-agnostic ReAct pattern:
  1. `get_textbook_structure`: Navigates hierarchical outlines (*Titles → Chapters → Sections*).
  2. `get_relevant_chunks`: Retrieves granular, verified passages with 1-based citation IDs (`[1]`, `[2]`).
  3. `get_media_and_tables`: Fetches authentic figures, diagrams, and structured tables with semantic captions and descriptions.
* **Table-First Logic (Zero Synthetic Flowcharts)**: Replaces fragile synthetic flowcharts with clean, accessible Markdown tables for comparisons, criteria, and multi-step decision workflows ($1 \rightarrow 2 \rightarrow 3$).
* **Authentic Column-Aware Figure Cropping**: PyMuPDF-powered extraction automatically detects visual plates, isolates multi-column text gutters to prevent adjacent-column bleed, and renders crisp 180 DPI JPEG figures served via a responsive carousel.
* **Visual Presentation Layer & Typography Normalization**: Sanitizes LaTeX tags, normalizes ion and hormone formulas (`T₄`, `TRβ₂`, `Na⁺/K⁺-ATPase`, `Mg²⁺`, `≥`, `≤`), balances Markdown, and converts textbook bibliography brackets into non-colliding `(Ref X)` text so only verified passages open interactive Evidence Drawer cards.
* **Dual-Scroll Clinical Workspace & Mobile Design System**: Responsive UI featuring independent dual-scroll containers (consultation history and active textbook scope), touch targets $\ge 44 \times 44\text{px}$, backdrop drawer overlays, and full WCAG AA compliance.
* **Strict User Selection Sovereignty**: Allows clinicians to activate or deactivate specific textbooks in their personal library; user choices are strictly respected by the retrieval engine.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 Textbook Canon Ingestion Pipeline               │
│                                                                 │
│  PDF → Page Map → Section Tree → Headings → Column-Gutter Sort  │
│       → Tag Blocks (Tables/Boxes/Figures) → Bounded Chunks     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │     SQLite FTS5 /   │
                    │  PostgreSQL+pgvector │
                    └──────────┬──────────┘
                               │
            ┌───────────────────▼───────────────────┐
            │        Universal Retrieval Layer      │
            │  get_textbook_structure · get_chunks  │
            │  get_media_and_tables · parallel.py   │
            └───────────────────┬───────────────────┘
                               │
            ┌───────────────────▼───────────────────┐
            │       Universal Agent Engine          │
            │  Direct Answer First · ReAct Engine   │
            │  Gemini 2.0 Flash / OpenAI / Offline  │
            │  Visual Presentation Layer & Normalizer│
            └───────────────────┬───────────────────┘
                               │
            ┌───────────────────▼───────────────────┐
            │         CliniSource Web Platform      │
            │  Evidence Drawer · Live SSE Stream    │
            │  Authentic Diagram Plate Carousel     │
            │  My Clinical Canon Library Manager    │
            └───────────────────────────────────────┘
```

---

## Quickstart

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/argv26/CliniSource.git
cd CliniSource

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Set GEMINI_API_KEY (optional: CliniSource functions fully offline with local synthesizer)
```

### 3. Start the CliniSource Platform

```bash
python -m ui.app
# Open http://127.0.0.1:8000 in your browser
```

---

## Ingesting Reference Volumes

Place PDF reference works into `ingestion/test-books/` and execute the pipeline:

```bash
# Ingest all reference volumes in the directory:
python run_pipeline.py --all

# Or ingest an individual volume:
python run_pipeline.py --book "Williams Textbook of Endocrinology"
```

Alternatively, drag and drop any reference PDF directly into the **Clinical Reference Canon** upload modal in the web interface for automatic background extraction and indexing.

---

## CLI Retrieval & Auditing

You can query the underlying knowledge base directly from the terminal:

```bash
# Search section outline headings
python -m retrieval.tools search-sections "adrenal cortex"

# Search specific passages, tables, and callouts
python -m retrieval.tools search-chunks "cortisol synthesis" --limit 10

# Read a full section in continuous reading order
python -m retrieval.tools read-section --book Williams_Textbook_of_Endocrinology_15th_edition_2 --section-id 6

# Inspect table of contents hierarchy
python -m retrieval.tools get-toc --book anatomy-and-physiology-2e_-_WEB
```

---

## Key Features

| Feature | System & Clinical Impact |
|---|---|
| **Direct Answer First** | Conceptual and general queries receive an instant 2–3 paragraph answer with **0 retrieval latency and 0 tool calls**. |
| **Reference On-Demand** | Statutory, clinical, and scientific questions trigger dynamic 3-tool retrieval (`get_textbook_structure`, `get_relevant_chunks`, `get_media_and_tables`). |
| **Table-First Logic** | Comparisons, clinical criteria, drug dosings, and classifications format into clean, responsive Markdown tables with zero synthetic flowchart syntax issues. |
| **Column-Aware Diagram Cropping** | Crops authentic textbook plates at 180 DPI while strictly bounding text gutters to prevent column bleed; rejects pages without visual plates. |
| **Visual Presentation Layer** | Sanitizes raw LaTeX tags, standardizes ion typography (`Na⁺/K⁺-ATPase`), auto-balances markdown, and isolates citation pills. |
| **Specialty Canon Routing** | User selection sovereignty guarantees explicit textbook choices are strictly honored, with smart routing across multi-volume libraries. |
| **Dual-Scroll Clinical Workspace** | Independent scrolling containers for active consultations and personal textbook curation with live scope pills. |
| **Mobile-First Responsive Design** | Full viewport adaptability across mobile, tablet, and desktop with accessible drawer overlays and $\ge 44 \times 44\text{px}$ touch targets. |
| **Dynamic Ingestion Worker** | Drag-and-drop PDF upload with background worker, TOC extraction, reading-order sorting, and atomic DB commit. |
| **Printed Page Provenance** | Every answer cites the verified printed page number from physical textbook editions with interactive Evidence Drawer navigation. |
| **Production Concurrency** | SQLite Write-Ahead Logging (WAL mode), thread-locked atomic rate limiting, and 100% automated test coverage (101/101 tests passed). |

---

## Engineering Documentation

- 🏗️ **[System Architecture & Design Guide](docs/architecture.md)**: Deep dive into the two-layer architecture, modular packages, and database schema.
- 🩺 **[Agent Reasoning & Presentation Engine](docs/clinical-agent.md)**: How the universal ReAct engine, prompt caching, on-demand tools, and sanitizers operate.
- 📑 **[Medical Canon Ingestion Pipeline](docs/ingestion-pipeline.md)**: How PDFs are parsed, TOC trees built, columns sorted, and figures cropped.
- 💬 **[User Feedback & Production Solutions](docs/user-feedback.md)**: Itemized clinical feedback from testing sessions, usability observations, and architectural solutions.
- 🔌 **[HTTP REST & SSE API Reference](docs/api-reference.md)**: Complete endpoint schemas, request/response bodies, and Server-Sent Event types.
- 📋 **[Universal Implementation & Verification Specification](docs/universal-rag-implementation-plan.md)**: System verification, acceptance criteria, and test coverage documentation.
- 🚀 **[Production Deployment Guide](docs/deployment-guide.md)**: Containerization, environment setup, and instructions for deploying to **Render** or **Google Cloud Run**.

---

## Reference Canon Indexed

The production deployment includes comprehensive, pre-indexed reference masterworks:

| Textbook Title | Edition | Total Pages | Sections | Chunks Indexed | Specialty |
|---|---|---|---|---|---|
| **Harrison's Principles of Internal Medicine** | 22nd Edition (2025) | 4,273 | 591 | 16,963 | Internal Medicine |
| **Williams Textbook of Endocrinology** | 15th Edition | 2,319 | 2,944 | 9,016 | Endocrinology |
| **Anatomy and Physiology** | 2nd Edition (OpenStax) | 1,347 | 409 | 3,240 | Basic Medical Science |
| **Cornea: Fundamentals, Diagnosis & Management** | 5th Edition | 1,265 | 320 | 4,812 | Ophthalmology |

---

## Production Deployment

The application is fully containerized and self-contained with a pre-indexed clinical database:

```bash
docker compose up -d web
# Access at http://localhost:8000
```

---

## License

Designed for clinical decision support research, educational reference retrieval, and multi-domain knowledge workflows.
