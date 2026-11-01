# Scope Ideas & Future Roadmap

This document captures high-level scope ideas, architectural enhancements, and advanced clinical modules deferred beyond Phase 3.

---

## 1. Original Scope Ideas
- **Agentic Ingestion Pipeline**: Make parsing and extracting the textbook an autonomous agentic workflow (profiling, column detection, table-of-contents alignment).
- **Decoupled Media Storage**: Store high-resolution textbook figure images and plates in cloud object storage (AWS S3 / Cloudflare R2) rather than local repositories.

---

## 2. Cross-Textbook Discrepancy & Contrarian Opinion Resolver
*(Deferred from Phase 3 to maintain focus on multi-book scaling and UI routing)*

### Overview
When scaling to a library of 50+ textbooks across different medical eras and publishing bodies, textbooks will occasionally state conflicting facts (e.g., differing diagnostic thresholds for diabetes or gestational hypertension, differing anatomical branching definitions, or divergent first-line vs. second-line pharmacotherapy choices).

Standard RAG models often hallucinate an artificial compromise between conflicting numbers. This module implements a structured **Clinical Hierarchy of Evidence** and transparent contradiction reporting.

### Key Tenets
1. **Clinical Hierarchy of Evidence**:
   - **Subspecialty Authority**: Subspecialty gold-standard volumes (e.g., *Williams Textbook of Endocrinology*) supersede generalist basic-science texts (e.g., *Anatomy & Physiology*) on specialized pathophysiological and management nuances.
   - **Edition Recency & Guideline Evolution**: Newer textbook editions and updated society guidelines supersede historical consensus.
   - **Variant Recognition**: Anatomical variations (e.g., celiac trunk branching, variations in the cystic artery) must be explicitly presented as documented anatomical variants rather than contradictions.

2. **Anti-Hallucination & Discrepancy Transparency**:
   - The model must strictly avoid inventing an ungrounded compromise (e.g., averaging 126 mg/dL and 140 mg/dL to 133 mg/dL).
   - The model must explicitly present both perspectives with dual page citations:
     > *"Note: Textbook sources present differing criteria on this threshold. According to Williams Endocrinology (p. 604)... whereas Anatomy & Physiology (p. 712) states... In clinical practice, the subspecialty guideline is typically prioritized."*

3. **Artifacts & Components to Build**:
   - Golden discrepancy benchmark dataset: `tests/fixtures/discrepancies.json`.
   - Contrarian citation preserver in `agent/sanitizers.py` to ensure dual conflicting citations remain clickable.
   - Dialectical prompt directives in `agent/prompts.py`.
   - Integration tests in `tests/integration/test_discrepancy_resolution.py`.

---

## 3. Dense Vector Embeddings & Hybrid Search Fusion
- Generate dense vector embeddings for textbook passages using `gemini-embedding` or local `sentence-transformers`.
- Reciprocal Rank Fusion (RRF) across FTS5 keyword hits and pgvector/FAISS dense similarity hits to capture clinical synonyms and semantic paraphrases.

---

## 4. Advanced Multi-Modal Medical Imaging (Vision Agents)
- Direct on-demand visual question answering for complex histopathology, clinical micrographs, and radiology plates using multimodal foundation models with high-resolution crop coordinates.

---

## 5. Real-Time PubMed & Clinical Guideline Live Bridge
- Dynamic federation between offline indexed textbook volumes and live PubMed/UpToDate guideline updates to flag outdated textbook recommendations.

---

## 6. Frontend Architecture Evolution: React Migration (Vite + React + Tailwind)

### Motivation
The existing frontend is implemented in vanilla JavaScript (~2,000 lines in `app.js`) served directly from FastAPI. While zero-build and fast to run without Node.js, scaling to a multi-view application (Chat, Evidence Drawer, Multi-Book Library Manager, Upload Progress, Citation Modals) strains imperative DOM manipulation and fragmented global state.

### Proposed Architecture
- **Framework**: Vite + React + TypeScript + Tailwind CSS.
- **State Management**: Zustand / React Query for centralized server state, consultation sessions, and active textbook scopes.
- **Component Decomposition**:
  - `<HeaderNavigation />`: Tab switching between Consultation and Library Manager.
  - `<Sidebar />`: Dual-scroll history and active book toggles.
  - `<ChatStream />`: Progressive token rendering, citation pill badges, and Mermaid flowcharts.
  - `<LibraryManager />`: User Library vs. Global Catalog browsing with specialty accordions.
  - `<EvidenceDrawer />`: Slide-out panel for textbook excerpts and diagram lightbox.
  - `<IngestionModal />`: Drag-and-drop PDF upload with background worker progress bar.
- **Backend Bridge**: FastAPI remains pure headless API server; Vite proxies in development and builds static bundle to `ui/dist` for production.


