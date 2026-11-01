# ISSUE-001: Ingestion Worker Ignores Pre-Configured Job Slug and Overwrites on Ingestion

- **Status**: RESOLVED
- **Date**: 2026-11-01
- **Segment**: Segment 1: Ingestion & Document Pipeline
- **Failure Code**: F4 Assertion Mismatch / F5 Missing State Sync
- **Severity / Urgency**: P1 (High Consistency Gap)

---

### 1. Observable Symptom & Error
In `tests/integration/test_segment1_ingestion.py::test_end_to_end_pipeline_success`:
```text
> assert search_results[0]["book_slug"] == "endocrine_disorders"
E AssertionError: assert 'Endocrine_Disorders_Guide' == 'endocrine_disorders'
```

### 2. Reproduction Evidence
- **Reproduction Command**: `.\.venv\Scripts\python -m pytest tests/integration/test_segment1_ingestion.py -k test_end_to_end_pipeline_success`
- **Observed Result**: `create_job` registers `job.book_slug = "endocrine_disorders"`. However, during `run_ingestion_pipeline`, line 589 hardcodes `book_slug = generate_book_slug(title)` (`"Endocrine_Disorders_Guide"`), ignoring the existing `job.book_slug` and overwriting it in the database and completion job dictionary.
- **Expected Result**: If `job.book_slug` is explicitly configured during job creation (or passed as an argument), `run_ingestion_pipeline` must honor `job.book_slug` instead of unconditionally recalculating and overwriting it from `title`.

### 3. Root Cause Analysis
In `ingestion/pipeline_worker.py`:
- `create_job(job_id, title, specialty, book_slug)` accepts and stores a caller-provided slug.
- In `run_ingestion_pipeline(...)`, line 589 directly calls `book_slug = generate_book_slug(title)`. It never inspected `job.book_slug`.

### 4. Remediation Plan & Code Fix
1. In `ingestion/pipeline_worker.py:run_ingestion_pipeline`:
   - Added `book_slug: str | None = None` optional parameter.
   - Retrieved the pre-registered job: `current_job = get_job(job_id)`.
   - Resolved slug as:
     `resolved_slug = book_slug or (current_job.book_slug if current_job and current_job.book_slug else None) or generate_book_slug(title)`
   - Used `book_slug = resolved_slug` during chunking, indexing, and completion updates.

### 5. Verification Proof
- `.\.venv\Scripts\python -m pytest tests/integration/test_segment1_ingestion.py`:
  - 8/8 tests PASSED in 0.42s.
- `test_end_to_end_pipeline_success` confirmed that the database book slug, chunks, and FTS5 search results accurately preserve the pre-configured job slug.
