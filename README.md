---
title: CliniSource
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
---

# CliniSource

### *The Authoritative Clinical Knowledge & Decision Intelligence Engine*

[![Tests](https://img.shields.io/badge/tests-72%20passed-success)](tests/)
[![Architecture](https://img.shields.io/badge/architecture-structure--aware-blue)](docs/architecture.md)
[![Clinical Reasoning](https://img.shields.io/badge/clinical--reasoning-AttendingPlanner-indigo)](docs/clinical-agent.md)
[![License](https://img.shields.io/badge/license-clinical--research-slate)](LICENSE)

CliniSource is an enterprise-grade clinical decision intelligence platform that arms clinicians, residents, and medical researchers with the verified canon of human medicine in under 500 milliseconds.

> 🚀 **Live Production Deployment**: [https://text-book-rag-etiz.onrender.com](https://text-book-rag-etiz.onrender.com)  
> 🏗️ **Architecture & Design**: [docs/architecture.md](docs/architecture.md) | 🩺 **Clinical Reasoning Guide**: [docs/clinical-agent.md](docs/clinical-agent.md)

---

## The Clinical Problem

Modern clinical decision support faces an unsustainable trilemma:

1. **The Hallucination Hazard**: Generalist LLMs (e.g. ChatGPT, Claude) generate fluent, confident clinical advice that often fabricates dosages, cites nonexistent clinical trials, or conflates conflicting specialty guidelines. In medicine, "probably correct" is a patient safety violation.
2. **The 15-Minute "Scrolling Tax"**: Incumbent reference tools (UpToDate, DynaMed, monolithic PDFs) are exhaustive but slow. Clinicians must manually scroll through 40-page monographs to find a single drug titration guideline or contraindication while a patient waits.
3. **The Geometric Failure of Generic RAG**: Medical reference literature is architecturally complex—relying on two-column gutters, diagnostic decision trees, cross-tabulated dosages, and anatomical figures. Standard vector chunkers flatten tables into unintelligible text, mangle reading gutters, lose printed pagination, and strip crucial diagnostic diagrams.

---

## The CliniSource Solution

CliniSource bridges the gap between gold-standard medical reference canon (*Harrison's Internal Medicine*, *Williams Endocrinology*, *Robbins Pathology*) and instant bedside decision support:

* **The Attending Mindset (`AttendingPlanner`)**: Formulates differential diagnostic hypotheses and affected organ systems before retrieval, streaming clinical plans live over Server-Sent Events (SSE).
* **Structure-Aware Document Geometry**: Ingestion preserves multi-column reading gutters, restores publisher heading hierarchies (`Part → Chapter → Section → Subsection`), and reconciles PDF coordinates with physical printed page numbers.
* **Dual-Ledger Auditability**: Every synthesized sentence is anchored to interactive citation pills backed by exact printed page coordinates and source chapters in the Evidence Drawer. Zero trust required—complete accountability guaranteed.
* **Instant Visual Streaming**: Diagnostic algorithms, histological slides, and anatomical diagrams stream natively alongside clinical synthesis via SSE with zero multimodal LLM latency.
* **Multi-Volume Specialty Routing**: Strict user sovereignty honors explicit library filters, while smart semantic routing intelligently routes cross-disciplinary inquiries to the top relevant reference works.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 Medical Canon Ingestion Pipeline                │
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
           │        Specialized Retrieval Layer    │
           │  search_sections · search_chunks      │
           │  read_section · get_toc · get_chunk   │
           └───────────────────┬───────────────────┘
                               │
           ┌───────────────────▼───────────────────┐
           │   Attending Clinical Agent Engine     │
           │  AttendingPlanner Pre-Step Reasoner   │
           │  Gemini / OpenAI / Offline Fallback   │
           │  Citation Integrity Sanitizer         │
           └───────────────────┬───────────────────┘
                               │
           ┌───────────────────▼───────────────────┐
           │      CliniSource Web Consultation     │
           │  Evidence Drawer · Live Plan Stream   │
           │  Zero-Multimodal Figure Carousel      │
           │  My Clinical Canon Library Manager    │
           └───────────────────────────────────────┘
```

---

## Quickstart

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/argv26/Text-Book-RAG.git
cd Text-Book-RAG

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
# Set GEMINI_API_KEY or OPENAI_API_KEY (optional: CliniSource works fully offline with local synthesizer)
```

### 3. Start the CliniSource Platform

```bash
python -m ui.app
# Open http://127.0.0.1:8000 in your browser
```

---

## Ingesting Reference Volumes

Place PDF medical reference works into `ingestion/test-books/` and execute the pipeline:

```bash
# Ingest all reference volumes in the directory:
python run_pipeline.py --all

# Or ingest an individual volume:
python run_pipeline.py --book "Williams Textbook of Endocrinology"
```

Alternatively, drag and drop any medical reference PDF directly into the **Clinical Reference Canon** upload modal in the web interface for automatic background indexing.

---

## CLI Retrieval & Auditing

You can query the underlying clinical knowledge base directly from the terminal:

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

| Feature | Clinical Impact |
|---|---|
| **AttendingPlanner Reasoning** | Formulates differential diagnostic hypotheses and organ systems before retrieval, streaming clinical plans live over SSE. |
| **Structure-Aware Chunking** | Chunks never cross section boundaries; tables, callout boxes, and figure captions are typed and indexed separately. |
| **Specialty Canon Routing** | User selection sovereignty guarantees explicit textbook choices are strictly honored, while smart routing directs broad queries. |
| **Zero-Multimodal Figure Carousel** | Pre-crops textbook diagrams into Object Storage; serves visual plates via responsive carousel without consuming LLM vision tokens. |
| **Dual-Scroll Clinical Workspace** | Dual-scroll layout separates consultation history from personal "Clinical Reference Canon" curation with 1-click active switches. |
| **Dynamic Ingestion Worker** | Drag-and-drop PDF upload with non-blocking background worker, automatic TOC extraction, reading-order sorting, and atomic DB commit. |
| **Printed Page Provenance** | Every answer cites the verified printed page number from physical textbook editions with interactive Evidence Drawer navigation. |
| **Medical Typography Normalization** | Sanitizes hormone LaTeX formulas (`T₄`, `TRβ₂`) and converts publisher bibliography brackets into non-colliding `(Ref X)` text. |
| **Production Concurrency** | SQLite WAL mode, atomic thread-locked rate limiting, and 100% automated integration test coverage. |

---

## Engineering Documentation

- 🏗️ **[System Architecture & Design Guide](docs/architecture.md)**: Deep dive into the two-layer architecture, modular packages, and SQLite schema.
- 🩺 **[Clinical Agent & Reasoning Engine](docs/clinical-agent.md)**: How AttendingPlanner, prompt caching, ReAct loops, and sanitizers operate.
- 📑 **[Medical Canon Ingestion Pipeline](docs/ingestion-pipeline.md)**: How PDFs are parsed, TOC trees built, columns sorted, and figures cropped.
- 💬 **[User Feedback & Evolution Log](docs/user-feedback.md)**: Itemized clinical feedback from testing sessions, pain points, and architectural solutions.
- 🔌 **[HTTP REST & SSE API Reference](docs/api-reference.md)**: Complete endpoint schemas, request/response bodies, and Server-Sent Event types.
- 🚀 **[Production Deployment Guide](docs/deployment-guide.md)**: Containerization, environment setup, and instructions for deploying to **Render** or **Google Cloud Run**.

---

## Production Deployment

The application is fully containerized and self-contained with a pre-indexed clinical database:

```bash
docker compose up -d web
# Access at http://localhost:8000
```

---

## License

Designed for clinical decision support research and educational reference retrieval workflows.
