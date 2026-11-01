# Universal Textbook RAG: Generic Consultation Engine & Runtime Architecture

This document establishes the architecture for the **Universal Textbook RAG Engine**. It transitions the system from a hardcoded medical-only prototype into a **domain-agnostic, tool-augmented textbook intelligence platform** that works seamlessly across **Law, Medicine, Engineering, Science, and Academia**.

---

## 1. Core Principles & Motivation

Earlier versions suffered from critical production issues:
1. **Domain Over-Specialization**: Hardcoded medical attending prompts and rigid organ-system planners that break when applied to other domains like Law or Engineering.
2. **The Context-Dumping Trap**: Dumping 3,000+ words of raw textbook passages into the prompt, combined with a rigid system prompt mandating 6-heading monographs (2,000+ words) even for simple queries.
3. **Synthetic Flowchart Fragility**: Generating synthetic Mermaid flowchart code caused syntax crashes, bomb icons, unquoted pipe errors, and distorted shapes.
4. **Typography Glitches**: Stray LaTeX math signs (`15$`, `35$`) and broken multi-column tables.

### The Universal V2 Philosophy:
* **Generic Across Domains**: A law student querying statutory provisions and case law, a medical student querying endocrine pathways, and an engineer querying thermodynamic cycles use the **same underlying engine**.
* **Zero Synthetic Flowcharts (Removed Completely)**: Synthetic flowcharts (Mermaid) are completely eliminated. All procedural and sequential logic is represented via **clean Markdown tables**, **crisp numbered decision steps ($1 \rightarrow 2 \rightarrow 3$)**, or **authentic textbook algorithm plates** cropped directly from the source PDF.
* **Tools on Demand (No Forced Retrieval)**: If a question is generic or conversational, the model answers directly with zero search latency. Textbook tools are invoked only when statutory, factual, or textbook proof is needed.
* **Semantic Media Selection**: Images, diagrams, and tables are retrieved with their **captions and semantic descriptions**. The LLM evaluates these descriptions and displays only what is truly relevant.
* **The Visual Presentation Layer (The Final Phase)**: A dedicated runtime formatting and normalization layer that guarantees clean tables, authentic figure plates, scrubbed typography, and interactive citation pills.

---

## 2. Universal Architecture Overview

```
                                  USER QUERY
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │   LLM (Gemini 2.0 Flash)  │ (Ultra-fast, Top Free Tier)
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

## 3. The 3 Universal Tools for the LLM

Instead of complex hardcoded pipelines, the LLM is equipped with 3 domain-agnostic tools:

### Tool 1: `get_textbook_structure`
* **Purpose**: Inspects the hierarchical outline, table of contents, and headings of indexed textbooks matching the given keywords or book slug.
* **Domain Behavior**:
  * **Law**: Returns *Title → Chapter → Statutory Section / Article* (e.g., *Title 18 > Chapter 47 > § 1001: Statements or entries generally*).
  * **Medicine**: Returns *Part → Chapter → Clinical Topic* (e.g., *Harrison's > Part 10: Disorders of the Kidney > Chapter 304: Fluid and Electrolyte Disturbances*).
  * **Engineering**: Returns *Unit → Topic → Theorems & Equations*.
* **Benefit**: Gives the LLM high-level structural context so it can target exact sub-sections rather than guessing blind search terms.

### Tool 2: `get_relevant_chunks`
* **Purpose**: Retrieves granular, high-yield text passages, provisions, and definitions from specific sections or via semantic keyword search.
* **Parameters**: `query` (required), `book_slug` (optional), `section_id` (optional), `limit` (default: 6).
* **Benefit**: Delivers verified textbook excerpts directly to the LLM with 1-based citation IDs `[1]`, `[2]`.

### Tool 3: `get_media_and_tables`
* **Purpose**: Retrieves all diagrams, illustrations, algorithm plates, and structured tables within the matched scope, along with their **semantic captions and descriptions**.
* **Contract**:
  ```json
  [
    {
      "media_id": "Williams_15e_Fig_16_2",
      "type": "figure",
      "caption": "Fig. 16.2 Venous thromboembolism risk among women by age and oral contraceptive formulation.",
      "description": "Risk curve graph showing relative risk of VTE across age groups and progestin generations.",
      "page": 800,
      "thumbnail_url": "/api/figure/Williams_15e_Fig_16_2/image"
    },
    {
      "media_id": "Table_16_2",
      "type": "table",
      "caption": "TABLE 16.2 Medical Eligibility Criteria for Combined Contraceptives",
      "description": "Comparative matrix listing US MEC Category 3 and 4 contraindications including hypertension and smoking cutoffs.",
      "page": 799,
      "markdown": "| Condition | MEC Category | Risk Factors |\n|---|---|---|\n| Age ≥ 35 and smoking ≥ 15 cig/day | 4 | Absolute contraindication |"
    }
  ]
  ```
* **LLM Intelligence**: The LLM reads the `description` of each item. If the user asks about *VTE risk in OCP*, the LLM selects Fig. 16.2; if the user asks about *Anatomy of the Kidney*, it ignores Fig. 16.2. Only relevant media is embedded or emitted to the frontend.

---

## 4. Reference On-Demand (Generic Queries vs. Grounded Queries)

* **Generic / Conversational Mode**:
  * Queries like *"Hi"*, *"What is res judicata?"*, *"Explain how an internal combustion engine works"*, or *"Summarize the difference between civil and criminal burden of proof"*.
  * The LLM recognizes that no specific textbook chapter is needed.
  * **Action**: Answers directly in 2–3 structured, authoritative paragraphs.
  * **Latency**: 0 tool calls, immediate Time-to-First-Token (TTFT).

* **Textbook Reference Mode**:
  * Queries like *"What are the statutory defenses under Section 230?"*, *"What are the contraindications to combined oral contraceptives according to Williams?"*, or *"Show me the hypokalemia diagnostic workup"*.
  * The LLM identifies the need for verified statutory/textbook proof.
  * **Action**: Invokes `get_textbook_structure` → `get_relevant_chunks` → `get_media_and_tables`.
  * **Output**: Direct answer first, followed by clean Markdown tables or authentic textbook figures, with interactive `[1]` citation pills linked to the Evidence Drawer.

---

## 5. Procedural Logic & Algorithms (No Synthetic Flowcharts)

Synthetic flowchart generators (e.g. Mermaid) are prone to syntax errors, bomb icons, and unreadable geometry. 

In CliniSource V2, **flowcharts are completely replaced by two superior representations**:

### 1. Structured Step-by-Step Decision Tables
For algorithms, protocols, and multi-branch decision logic, the model outputs clean Markdown tables:

```markdown
| Step | Clinical / Legal Assessment | Findings / Threshold | Direct Action |
| :--- | :--- | :--- | :--- |
| **1** | Assess Serum Potassium & Rule Out Shift | Normal pH, no insulin/beta-agonists | Proceed to evaluate urinary potassium excretion. |
| **2** | 24-Hour Urine K⁺ or Spot K⁺/Cr Ratio | $< 20 \text{ mmol/day}$ | Extra-renal potassium loss (GI loss, inadequate intake). |
| **3** | Measure Blood Pressure & Renin/Aldo | $> 20 \text{ mmol/day}$ with Hypertension | Evaluate for Primary Aldosteronism or Cushing's. |
```

### 2. Authentic Textbook Algorithm Plates
When the textbook contains an authentic clinical or legal decision algorithm (e.g., Harrison's Fig. 304-2), the system surfaces the authentic cropped plate directly into the visual evidence carousel.

---

## 6. The Visual Presentation Layer (The Final Runtime Phase)

To eliminate manual prompt-tweaking, the final phase before streaming output to the client is an automated **Visual Presentation & Normalization Layer**:

```
Raw LLM Output
      │
      ▼
┌────────────────────────────────────────────────────────┐
│             VISUAL PRESENTATION LAYER                  │
├────────────────────────────────────────────────────────┤
│ 1. Markdown Table Formatting                           │
│    • Ensures clean | Header | Column | syntax.         │
│    • CSS renders responsive, rounded, shaded tables.   │
├────────────────────────────────────────────────────────┤
│ 2. Authentic Media Display                             │
│    • Renders verified textbook figure plates.          │
│    • Zero synthetic flowchart syntax crashes.          │
│    • Interactive lightbox zoom with full caption.      │
├────────────────────────────────────────────────────────┤
│ 3. Automated Typography Normalization                  │
│    • Strips stray math signs: 15$ → 15, 35$ → 35.      │
│    • Auto-balances unclosed ** bolding.                │
│    • Formats standard symbols: Na⁺, Mg²⁺, β, ≥, ≤.     │
├────────────────────────────────────────────────────────┤
│ 4. Citation Pill Binding                               │
│    • Converts [1], [2] to interactive Evidence pills.  │
└────────────────────────────────────────────────────────┘
      │
      ▼
Client SSE Stream
```

### Table UI Styling (`ui/static/styles.css`)
```css
/* Accessible, responsive clinical and legal tables */
.prose-custom table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin: 1rem 0;
  border-radius: 0.75rem;
  border: 1px solid #e2e8f0;
  overflow-x: auto;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.prose-custom th {
  background-color: #f8fafc;
  color: #1e293b;
  font-weight: 700;
  text-align: left;
  padding: 0.75rem 1rem;
  font-size: 0.8125rem;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  border-bottom: 1px solid #cbd5e1;
}

.prose-custom td {
  padding: 0.75rem 1rem;
  font-size: 0.875rem;
  color: #334155;
  border-bottom: 1px solid #f1f5f9;
  line-height: 1.5;
}

.prose-custom tr:nth-child(even) td {
  background-color: #fbfcfe;
}
```

---

## 7. Model Strategy: High Performance, Zero Cost

| Pipeline Role | Selected Engine | Tier / Pricing | Why Selected |
| :--- | :--- | :--- | :--- |
| **Response Generation & Tool Orchestration** | **Google Gemini 2.0 Flash** | **Free Tier** (15 RPM, 1M TPM, 1,500 RPD) | Ultra-low TTFT, 1M token context window, state-of-the-art native tool calling, completely free. |
| **Fallback Generator** | **OpenAI GPT-4o / GPT-4o-mini** | Paid / API key | Configured as automatic fallback if Gemini key is absent. |
| **Textbook Full-Text Search** | **SQLite FTS5 (BM25)** | **Local / 100% Free** | Instant local search (<5ms), zero network overhead, zero API rate limits, works offline. |
| **Semantic Dense Embeddings** | **Google text-embedding-004** | **Free Tier** | High semantic retrieval accuracy across multi-discipline text; fall back to local `all-MiniLM-L6-v2`. |
| **One-Time Document Extraction** | **Gemini 2.0 Flash Vision** | **~$0.10 / 1M tokens** | Parses 4,000-page books into structured tables and figure bounding boxes for ~$0.72 in ~5 minutes. |

---

## 8. What We Are Removing / Simplifying

To ensure the architecture remains generic and maintainable, the following legacy components are retired:

1. **Synthetic Flowcharts (Mermaid)**: Completely eliminated. No synthetic mermaid code blocks, no client-side mermaid crashes, zero bomb icons.
2. **`agent/planner.py` (`AttendingPlanner`)**: Retired. We no longer force medical organ systems or diagnostic hypotheses on non-medical queries. The LLM handles structural search naturally via tools.
3. **Mandatory 6-Heading Monograph Prompt**: Removed. Replaced with an agile, domain-agnostic instruction: *Direct Answer First → Markdown Tables for Criteria/Decisions → Relevant Figures with Captions → In-Text [1] Citations on Demand*.
4. **Domain-Specific Specialty Routers**: Replaced with clean user-selectable textbook scopes.

---

## 9. Verification & Quality Gates

Before marking any release complete:
1. **Generic Query Check**: Query *"What is consideration in contract law?"* → Answers directly in 2–3 crisp paragraphs with 0 tool calls and 0 forced medical terms.
2. **Table-First Quality Check**: Query *"Contraindications of OCP"* or *"Statutory exceptions to hearsay"* → Streams a clean, bordered Markdown table with proper columns.
3. **No Flowchart / Bomb Icon Verification**: Query *"hypokalemia evaluation"* → Emits a clean step-by-step decision table and authentic textbook plate; zero Mermaid code blocks, zero bomb icons anywhere in the UI.
4. **Figure Caption Alignment**: Query *"Venous thromboembolism in contraception"* → Displays Williams Fig. 16.2 from physical page 800 (not 996) with authentic caption and 100% visual fidelity.
5. **Automated Suite**: All 72 integration tests pass (`pytest tests/integration`).
