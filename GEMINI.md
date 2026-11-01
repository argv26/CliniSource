# Agent Workflow and Interaction Guidelines

These workflow guidelines govern all interactions in this project. You must strictly follow the three phases: **1. Understanding**, **2. Planning**, and **3. Implementation**. Do not skip phases or begin implementation autonomously without explicit approval.

---

## 1. Directory Structure Conventions

Maintain and utilize three dedicated directories:

1. `docs/`:
   - Overall design and architecture documents.
   - Shared decisions, constraints, and project context.
   - Incremental implementation plans with task-specific prompts.
   - Progress tracking, verification results, and remaining work.
   - *Source of truth for understanding progress across all sessions.*

2. `temp/`:
   - Reusable exploratory scripts, CLI commands, and temporary experiments.
   - Test inputs and generated artifacts for investigating or reproducing issues.
   - *Workspace to be reused across sessions; never regenerate scripts from scratch when an existing one can be reused or extended.*

3. `issues/`:
   - Production readiness issue reports and failure diagnostics (`ISSUE-<id>-<slug>.md`).
   - Root-cause analysis, reproduction commands, and resolution verifications.
   - *Source of truth for tracking bugs, regressions, and production gaps until resolved.*

---

## 2. Phase 1: Understanding — Explore Before Solving

When asked to understand, explore, or investigate a problem or feature:

- **Targeted exploration**: Explore only the relevant parts of the codebase:
  - The basic building blocks of the system.
  - How the relevant components interact.
  - The APIs, contracts, and interfaces involved.
  - The existing implementation and key design decisions.
- **Scope control**: Start with the high-level architecture and follow only the execution paths relevant to the task. Do not read the entire codebase or delve into unrelated implementation details.
- **Source of truth**: Use existing documentation and code as sources of truth. Distinguish verified facts from assumptions.
- **Interactive discussion**: Treat this phase as an interactive technical discussion. Explain concepts in simple terms, answer questions, and help build a mental model before proposing solutions.
- **Focus**: Keep responses focused on the question being discussed. Do not repeatedly summarize the entire system.
- **Constraints**:
  - Do **not** implement features or modify production code.
  - If a small exploratory script or command helps investigate, place it in or reuse from `temp/`.
  - If something important is unclear, investigate it together; do not jump to solutions prematurely.

---

## 3. Phase 2: Planning — Decide What to Build

When designing or planning changes:

- **Pre-planning review**: Read relevant project documentation in `docs/` (overall design, shared decisions, current plan/progress).
- **Interactive collaboration**:
  - Review the problem statement and proposed approach.
  - Identify gaps, potential issues, trade-offs, and simpler alternatives.
  - Help arrive at the best solution through conversation.
- **Constraints during planning**:
  - Do **not** generate implementation code.
  - Do **not** modify production code or configuration files.
  - Do **not** create or modify project files without explicit user approval.
  - Do **not** begin autonomous implementation.
  - Answer specific questions using established context; investigate additional files only when needed.
- **Plan creation**: Once agreed on the solution, produce an incremental implementation plan with steps that are as small and independent as reasonably possible.
  - For every step, provide:
    1. A simple description of what needs to be done and why.
    2. A self-contained prompt suitable for a fresh agent session.
    3. Relevant files, components, documentation, and dependencies.
    4. Clear acceptance criteria.
    5. Simple, human-verifiable steps with expected results for manual verification.
- **Approval gate**: Stop and ask if the implementation requires an unapproved design change, conflicts with existing behavior, or encounters unresolved decisions. **Do not begin implementation until the user explicitly approves the plan.**

---

## 4. Phase 3: Implementation — Execute, Understand, Verify

When executing an approved implementation step:

- **Pre-implementation check**: Read the overall design, shared decisions, current plan/progress, and the specific task prompt with its verification criteria.
- **Scope**: Implement **only** the single approved step, adhering strictly to agreed acceptance criteria.
- **Code quality guidelines**:
  - Write the simplest code that correctly solves the problem.
  - Use meaningful, human-readable variable, function, and class names.
  - Follow appropriate design principles (including SOLID where applicable) without unnecessary complexity or premature abstractions.
  - Reuse existing abstractions, scripts, and conventions.
  - Avoid hardcoding values that should be configurable.
  - Add appropriate error handling and useful logs without unnecessary noise.
  - Keep comments concise and explain intent rather than restating code.
  - Avoid unrelated refactoring or changes outside the approved scope.
- **Exploration & temporary artifacts**:
  - Reuse existing scripts from `temp/`.
  - Keep exploratory scripts and temporary artifacts separate from production code.
  - Preserve useful artifacts until the task is verified.
- **Verification protocol**:
  1. Run relevant automated tests and checks.
  2. Follow and document every human-verification step specified in the plan.
  3. Explain what the user should do, what to observe, and what the expected result means.
  4. Explicitly report any check that could not be run; never claim success without evidence.
  5. Do **not** skip human verification simply because automated tests pass.
- **Code review & explanation**:
  - Explain changes at the function and class levels.
  - Describe how modified code integrates into the existing system.
  - Highlight key design decisions, edge cases, and potential failure modes.
- **Documentation & progress tracking**:
  - Update the implementation plan in `docs/` with actual progress and verification results.
  - Update shared decisions and architecture documents if needed.
  - Record remaining work and unresolved issues.
  - Identify temporary files to be cleaned up before committing.
  - Never delete or overwrite unrelated user files.
- **Stop conditions**:
  - If implementation requires an unapproved design change, conflicts with the plan, or encounters ambiguity affecting correctness: **stop immediately, explain the issue, and ask for a decision**.
- **Completion summary**:
  - Summarize what changed and why.
  - Report pass/fail status for tests and human-verification steps.
  - Note what remains incomplete and follow-up actions required.
  - **Do not proceed to the next implementation step without user review and approval.**

---

## 5. UI/UX Design System Guidelines (UI Skill)

When designing, implementing, modifying, or reviewing user interfaces (pages, components, styles, interactions):

### Priority Rule Matrix

Follow priority 1 &rarr; 10 to guide design and implementation decisions:

| Priority | Category | Impact | Key Checks (Must Have) | Anti-Patterns (Avoid) |
|---|---|---|---|---|
| **1** | **Accessibility** | CRITICAL | Contrast &ge; 4.5:1, Alt text on media, Full keyboard navigation, Visible focus rings (`focus-visible`), Semantic aria-labels | Removing focus outlines, Icon-only buttons without `aria-label` or screen-reader text |
| **2** | **Touch & Interaction** | CRITICAL | Min touch target 44&times;44px (use pseudo-elements for compact badges), &ge;8px spacing between touch targets, Immediate active feedback | Hover-only interactions without touch equivalents, 0ms instant changes without transition feedback |
| **3** | **Performance** | HIGH | SVG / WebP assets, Lazy loading for offscreen media, Reserved container layout space (prevent Cumulative Layout Shift CLS &lt; 0.1) | Layout thrashing, Cumulative layout shifts, Unbounded asset downloads |
| **4** | **Visual Style & Consistency** | HIGH | Consistent theme tokens, Clean medical/clinical aesthetic, High-quality scalable SVG icons | Emoji as functional UI icons, Inconsistent card borders, Mixing mismatched design languages |
| **5** | **Layout & Responsive** | HIGH | Mobile-first breakpoints, Fluid containers, Responsive drawer/sidebar drawers, Zero horizontal page scroll | Horizontal overflow/clipping, Fixed pixel container widths, Disabled zoom |
| **6** | **Typography & Color** | MEDIUM | Base font 16px, Line-height &ge; 1.5 for body text, Minimum 12px floor (no sub-12px micro-text), Semantic color tokens (`--color-text`, `--color-surface`, `--color-border`) | Gray-on-gray unreadable low-contrast text, Raw disconnected hex values scattered in components |
| **7** | **Animation & Transitions** | MEDIUM | Context-aware timing (150&ndash;250ms), Ease-in-out / cubic-bezier curves, Respect `prefers-reduced-motion` | Universal identical durations for everything, Animating width/height instead of transform/opacity, Ignoring reduced-motion settings |
| **8** | **Forms & Inputs** | MEDIUM | Persistent visible field labels, Contextual helper text, Inline error states adjacent to the field, Clean focus-within styling | Placeholder-only inputs without labels, Error banners located far away from the relevant field |
| **9** | **Navigation & State** | HIGH | Predictable view switching, Clear active indicator pills and counters, Independent scrolling containers for dual lists | Squashed containers, Broken back navigation, Losing conversation state when switching views |
| **10** | **Data & Badges** | LOW | Distinct shape/badge styling alongside color (never rely on color alone), Live count pills, Accessible tooltips | Using only green/red color without text or iconography to signal status |

### Pre-Delivery UI Quality Checklist
Before marking any UI task complete:
1. **Focus & Keyboard Navigation**: Verify all interactive elements (buttons, inputs, toggles, tabs) can be focused via Tab and triggered with Enter/Space.
2. **Contrast Ratio**: Verify text meets WCAG AA contrast (4.5:1 for normal text, 3:1 for large text).
3. **Touch Targets**: Ensure touch targets are at least 44&times;44px.
4. **Responsive Integrity**: Ensure layout renders seamlessly on mobile (&lt;640px), tablet (&lt;1024px), and desktop (&ge;1024px) without horizontal scrolling.
5. **Independent Scrolling**: When multiple list containers share vertical space (e.g. Chat History and Library Books in the sidebar), ensure each has independent smooth scroll (`overflow-y: auto`) without vertical squishing.
6. **State Indicators**: Live indicators (active textbook counts, connection status, unread evidence) must update dynamically and reflect the ground truth.
7. **Reduced Motion**: Verify CSS includes `@media (prefers-reduced-motion: reduce)` to disable non-essential motion.

---

## 6. End-to-End (E2E) & Integration Testing Guidelines (Testing Skill)

> [!IMPORTANT]
> **Operational Scope Boundary**:
> This testing skill applies **strictly and exclusively** when authoring, reviewing, executing, or debugging automated test suites (unit, integration, fixture E2E, and service E2E).
> It does **not** alter, replace, or bypass the mandatory **3-Phase Workflow (1. Understanding → 2. Planning → 3. Implementation)** for product features, architectural changes, or codebase refactoring.

### 1. Test Lane Taxonomy & Annotations

Every test must operate in a clearly identified lane:

| Lane | Scope & Observable Boundary | Dependencies & Environment |
|---|---|---|
| `integration` | In-process module/API handlers, router integration, database queries | Real internal components; mock only external network/APIs outside the process. |
| `fixture-e2e` | Browser UI behavior with deterministic state | UI driven in browser; backend/LLM endpoints mocked via deterministic fixtures. |
| `service-integration-e2e` | Full system end-to-end flows across real service boundaries | Real local server, real SQLite DB, real retrieval pipeline (loopback only). |

**Test Skeleton Standard**:
Every integration and E2E test must document its contract in docstrings/comments:
```python
# AC: [Original acceptance criteria text]
# Behavior: [Trigger / Input] -> [Process / Action] -> [Observable Result]
# @lane: integration | fixture-e2e | service-integration-e2e
# @dependency: [none | sqlite | background-worker | full-system]
# Selection evidence: [Claim verified and why a cheaper test lane is insufficient]
```

### 2. The 3 Iron Rules of Test Integrity (Anti-Patterns to Avoid)

1. **Never Manufacture Green**:
   - Never weaken, widen, skip, or comment out an assertion to make a failing test pass.
   - When a test fails, decide the axis first: **Product Regression** (app bug to fix) vs. **Test Defect** (flawed test logic).
2. **Zero Tolerance for Silent Passes (P0 Smells)**:
   - **No swallowed errors**: Never wrap assertions in `try/except` or `.catch()` that silently ignore exceptions.
   - **No conditional assertions**: Never place load-bearing assertions inside an `if` statement where the test can silently skip verification.
   - **No vacuous assertions**: Ensure the assertion cannot pass trivially (e.g., verifying truthiness of an unawaited coroutine, empty list iteration, or tautology).
3. **No Band-Aid Timing (P1 Smells)**:
   - **No arbitrary fixed sleeps**: Never use `time.sleep(N)` or fixed timeouts to wait for async jobs or UI updates.
   - Always poll or await on explicit observable conditions (e.g., job status == 'completed', DOM selector attached, SSE event received) with bounded timeouts.

### 3. Failure Diagnostic Matrix (F1–F15)

When analyzing a test failure, classify the root cause before proposing any fix:

| Code | Category | Root Cause Signal | Correct Remediation |
|---|---|---|---|
| **F1** | **Flaky / Timing** | Intermittent failure near timeout; passes on isolated retry | Replace fixed wait with condition polling / event listener. |
| **F2** | **Selector Drift** | Element not found, selector mismatch, DOM changed | Update selector to semantic accessible target (`aria-label`, data-testid). |
| **F3** | **Network / Dependency** | Unexpected HTTP status (404/500), unmocked remote call | Ensure test server is running or stub boundary is properly configured. |
| **F4** | **Assertion Mismatch** | `expected X == Y`; actual outcome diverged | Investigate product regression; adjust assertion only if test was wrong. |
| **F5** | **Missing State Sync** | Action completed but downstream state not updated | Await background worker or async mutation completion before asserting. |
| **F7** | **Test Isolation Leak** | Passes alone, fails in full suite; state pollution | Reset SQLite tables, isolate temp directories, clear user session state. |
| **F9** | **Data Dependency** | Missing seeded fixtures, hardcoded IDs | Use dynamic test fixtures or setup factories instead of magic constants. |
| **F13** | **Error Swallowing** | Global exception handler hides underlying error | Re-raise unexpected errors; assert specific exception types. |
| **F14/F15**| **Animation / Hydration**| Interaction occurs mid-transition or before listener attached | Wait for DOM stability / transition end before dispatching click/input. |

### 4. Safety & Environment Boundary

- **Loopback Targets Only**: Automated E2E tests must only target local loopback origins (`localhost`, `127.0.0.1`, `::1`). Never execute tests against remote or staging/production URLs.
- **Disposable Test Data**: Tests that write to the database or file system must use isolated test databases (e.g. `test_textbook_rag.db`) or clean up their generated artifacts upon test teardown.
- **Credential Protection**: Never embed hardcoded API keys, tokens, or credentials in test specs or fixtures.

### 5. Production-Readiness Segmented Testing Protocol

When executing comprehensive system verification before release:
1. **Testing Segments**: Execute verification across the 6 core pillars:
   - *Segment 1*: Ingestion & Document Pipeline (scanned/DRM/corrupt PDFs, TOC fallbacks, semantic chunking, atomic commits).
   - *Segment 2*: Retrieval & Semantic Routing (FTS5 search, smart routing sovereignty, specialty filters).
   - *Segment 3*: Clinical Agent & SSE Streaming (AttendingPlanner, prompt cache, figure emission, stream integrity).
   - *Segment 4*: REST API & User Isolation (user libraries, session CRUD, multi-tenant state separation).
   - *Segment 5*: Frontend E2E & UI/UX (dual-scroll, upload modal, Evidence Drawer, responsive mobile, WCAG AA).
   - *Segment 6*: Concurrency & Stress (SQLite WAL concurrent reads/writes, async worker queues, load stability).
2. **Issue Logging Standard**:
   - For any failing test or production gap, immediately log `issues/ISSUE-<id>-<slug>.md` with reproduction evidence, F1–F15 classification, product impact, and proposed fix.
   - Never suppress or skip a failing test to move forward; all issues must be reviewed, resolved, and verified.




