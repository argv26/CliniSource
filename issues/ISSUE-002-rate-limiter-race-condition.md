# ISSUE-002: DailyRateLimiter TOCTOU Race Condition Under Burst Concurrency

- **Status**: RESOLVED
- **Date**: 2026-11-01
- **Segment**: Segment 6: Concurrency, Performance & Stress
- **Failure Code**: F5 Missing State Sync / F1 Flaky / Timing / Race Condition
- **Severity / Urgency**: P1 (Quota Bypass / Concurrency Gap)

---

### 1. Observable Symptom & Error
In `tests/integration/test_segment6_concurrency_stress.py::test_rate_limiter_burst_concurrency_race_safety`:
```text
>       assert allowed_count == 3, f"Expected exactly 3 allowed requests under limit=3, got {allowed_count}"
E       AssertionError: Expected exactly 3 allowed requests under limit=3, got 10
E       assert 10 == 3
```

### 2. Reproduction Evidence
- **Reproduction Command**: `.\.venv\Scripts\python -m pytest tests/integration/test_segment6_concurrency_stress.py -k test_rate_limiter_burst_concurrency_race_safety`
- **Observed Result**: When 10 concurrent threads make burst requests simultaneously for a user with `DAILY_REQUEST_LIMIT=3`, all 10 requests were approved (`allowed_count == 10`).
- **Expected Result**: Exactly 3 requests must be approved, and the remaining 7 requests must be rejected (`allowed_count == 3`, `denied_count == 7`).

### 3. Root Cause Analysis
In `ui/rate_limiter.py:check_and_increment`:
- The rate limiter executes a deferred read: `SELECT count FROM daily_usage WHERE client_id = ? AND day = ?;`.
- Because SQLite transactions default to deferred and no process-level lock or immediate write lock was held prior to the query, all 10 concurrent threads read `current_count = 0` before any thread committed its increment.
- Each thread then concluded that `current_count (0) < limit (3)` and executed `INSERT ... ON CONFLICT DO UPDATE SET count = 1`.
- As a consequence, 10 requests were allowed instead of 3, causing quota overselling under burst traffic.

### 4. Remediation Plan & Code Fix
1. In `ui/rate_limiter.py`:
   - Introduced a class-level thread lock `_lock = threading.Lock()` to serialize check-and-increment operations within the application process.
   - Used `conn.execute("BEGIN IMMEDIATE;")` inside the database transaction to acquire an immediate write lock in SQLite, ensuring atomic read-modify-write across multiple processes/workers.
   - Transaction automatically commits when the `with conn:` block exits cleanly.

### 5. Verification Proof
- Executed `.\.venv\Scripts\python -m pytest tests/integration/test_segment6_concurrency_stress.py -k test_rate_limiter_burst_concurrency_race_safety`:
  - 1/1 passed with exactly 3 allowed and 7 denied under 10 concurrent threads.
- Executed full Segment 6 suite:
  - 8/8 tests PASSED in 2.16s.
