# Production Issues & Verification Registry

This directory contains production gap reports, test failure reproductions, and remediation tracking for the CliniSource system.

---

## Issue Registry

| Issue ID | Slug | Segment | Code | Severity | Status |
|---|---|---|---|---|---|
| [ISSUE-001](file:///c:/Users/govin/Desktop/projects/Text-Book-RAG/issues/ISSUE-001-slug-discrepancy.md) | Ingestion Worker Slug Discrepancy | Segment 1: Ingestion | F4 / F5 | P1 | **RESOLVED** |
| [ISSUE-002](file:///c:/Users/govin/Desktop/projects/Text-Book-RAG/issues/ISSUE-002-rate-limiter-race-condition.md) | Rate Limiter TOCTOU Race Condition Under Burst | Segment 6: Concurrency | F1 / F5 | P1 | **RESOLVED** |

---

## Issue Template (`ISSUE-<id>-<slug>.md`)

```markdown
# ISSUE-[ID]: [Brief Title]

- **Status**: [OPEN | IN_PROGRESS | RESOLVED]
- **Date**: YYYY-MM-DD
- **Segment**: [Segment 1: Ingestion | Segment 2: Retrieval | Segment 3: Agent | Segment 4: API | Segment 5: UI/UX | Segment 6: Concurrency]
- **Failure Code**: [F1–F15 Code, e.g., F4 Assertion Mismatch, F7 Isolation Leak]
- **Severity / Urgency**: [P0 Silent Pass / Critical | P1 Intermittent / High | P2 Maintenance / Low]

---

### 1. Observable Symptom & Error
[Error message, traceback, or unexpected behavior]

### 2. Reproduction Evidence
- **Reproduction Command / Script**: `.\.venv\Scripts\python temp/repro_<slug>.py`
- **Observed Result**: [What actually happened]
- **Expected Result**: [What should have happened according to AC]

### 3. Root Cause Analysis
[Diagnosis of why the system failed: Product Regression vs. Flawed Spec]

### 4. Remediation Plan & Code Fix
[Files to be modified and proposed fix]

### 5. Verification Proof
[Command run and proof that the issue is resolved without regressions]
```

