# CliniSource: HTTP & SSE API Reference

This document provides the complete HTTP REST and Server-Sent Events (SSE) API specification for the CliniSource Knowledge & Clinical Decision Intelligence platform.

---

## 1. Authentication Endpoints

CliniSource supports both registered user accounts and instant 1-click ephemeral guest accounts. Sessions are maintained via `auth_session` HTTP-only cookies and Bearer tokens.

### `POST /api/auth/signup`
Creates a standard registered account.
- **Request Body (`application/json`)**:
  ```json
  {
    "username": "dr_house",
    "password": "secretpassword"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "user": {
      "id": "usr_9b1a8c...",
      "username": "dr_house",
      "is_guest": false
    },
    "token": "tok_4f2d7e..."
  }
  ```
- **Sets Cookie**: `auth_session` (`HttpOnly`, `SameSite=Lax`, `Max-Age=2592000`, `Path=/`)

### `POST /api/auth/login`
Authenticates existing credentials.
- **Request Body (`application/json`)**:
  ```json
  {
    "username": "dr_house",
    "password": "secretpassword"
  }
  ```
- **Response `200 OK`**: User profile and session token.

### `POST /api/auth/guest`
Generates an ephemeral 1-click guest identity with no password required.
- **Response `200 OK`**:
  ```json
  {
    "user": {
      "id": "guest_a1b2c3...",
      "username": "guest_a1b2c3",
      "is_guest": true
    },
    "token": "tok_9z8y7x..."
  }
  ```

### `GET /api/auth/me`
Retrieves the currently authenticated user profile, or `{ "user": null }` if unauthenticated.
- **Response `200 OK`**:
  ```json
  {
    "user": {
      "id": "usr_...",
      "username": "dr_house",
      "is_guest": false
    }
  }
  ```

### `POST /api/auth/logout`
Invalidates active session token and clears the `auth_session` cookie.
- **Response `200 OK`**: `{ "success": true }`

---

## 2. Consultation Sessions Endpoints

### `GET /api/sessions`
Lists all consultation sessions owned by the active user/guest ordered by most recent activity.
- **Response `200 OK`**:
  ```json
  {
    "sessions": [
      {
        "id": "ses_4a1b...",
        "title": "Adrenal Cortex Zonation & Aldosterone Synthesis",
        "message_count": 4,
        "created_at": "2026-11-01T12:00:00Z",
        "updated_at": "2026-11-01T12:05:00Z"
      }
    ]
  }
  ```

### `POST /api/sessions`
Initializes a new consultation session.
- **Request Body (`application/json`)**:
  ```json
  {
    "title": "New Consultation"
  }
  ```
- **Response `200 OK`**: Session object with generated session ID.

### `GET /api/sessions/{session_id}`
Retrieves session metadata, complete message history, and accumulated citations.
- **Response `200 OK`**:
  ```json
  {
    "session": { "id": "ses_...", "title": "..." },
    "messages": [
      {
        "role": "user",
        "content": "What are the primary contraindications of oral contraceptives?"
      },
      {
        "role": "assistant",
        "content": "...",
        "citations": [ ... ],
        "figures": [ ... ]
      }
    ]
  }
  ```

### `PATCH /api/sessions/{session_id}`
Updates a session title manually.
- **Request Body (`application/json`)**:
  ```json
  {
    "title": "OCP Contraindications & VTE Risk"
  }
  ```
- **Response `200 OK`**: Updated session object.

### `DELETE /api/sessions/{session_id}`
Deletes a consultation session and cascade-deletes all associated messages.
- **Response `200 OK`**: `{ "success": true, "session_id": "ses_..." }`

---

## 3. Chat & Streaming Endpoints

### `POST /api/chat`
Processes a synchronous conversational turn.
- **Request Body (`application/json`)**:
  ```json
  {
    "session_id": "ses_...",
    "message": "What is the classic clinical triad of DKA?",
    "book_slug": "Harrison_2025_22nd_Edition",
    "active_books": ["Harrison_2025_22nd_Edition", "Williams_Textbook_of_Endocrinology_15th_edition_2"]
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "reply": "The classic clinical triad of Diabetic Ketoacidosis (DKA) comprises...\n\n| Triad Component | Diagnostic Cutoff | Clinical Mechanism |\n|---|---|---|\n| Hyperglycemia | Blood glucose > 250 mg/dL | Absolute or relative insulin deficiency |\n| Ketosis | Moderate to severe ketonemia / ketonuria | Unchecked lipolysis & hepatic oxidation |\n| Metabolic Acidosis | Arterial pH ≤ 7.30, HCO₃⁻ ≤ 18 mEq/L | Accumulation of acetoacetate & β-hydroxybutyrate |\n\nPrompt fluid resuscitation with normal saline is indicated [1].",
    "citations": [
      {
        "citation_id": 1,
        "chunk_id": "Harrison_22e_ch416_s03_c012",
        "book_slug": "Harrison_2025_22nd_Edition",
        "book_title": "Harrison's Principles of Internal Medicine",
        "page_start": 2985,
        "page_end": 2986,
        "heading_path": "Part 12 > Disorders of Metabolism > Diabetes Mellitus"
      }
    ],
    "tool_calls": [
      {
        "name": "get_relevant_chunks",
        "args": { "query": "diabetic ketoacidosis triad hyperglycemia ketosis acidosis" }
      }
    ],
    "figures": [],
    "referenced_books": [
      {
        "slug": "Harrison_2025_22nd_Edition",
        "title": "Harrison's Principles of Internal Medicine",
        "specialty": "Internal Medicine",
        "pages": "pp. 2985–2986"
      }
    ]
  }
  ```

### `POST /api/chat/stream`
Processes a conversational turn with real-time Server-Sent Events (SSE).
- **Request Body**: Identical to `/api/chat`.
- **Response Header**: `Content-Type: text/event-stream`
- **Stream Event Types**:
  - `event: plan` — Emitted when differential hypotheses and search concepts are generated.
  - `event: status` — Status updates (`"Searching reference canon..."`).
  - `event: tools` — Tool execution telemetry (`get_textbook_structure`, `get_relevant_chunks`, `get_media_and_tables`).
  - `event: token` — Real-time token deltas (`{ "delta": "The " }`).
  - `event: citations` — Array of verified textbook citations bound to `[1]`, `[2]`.
  - `event: referenced_books` — Array of books referenced with formatted page ranges (`"pp. 800–802"`).
  - `event: figures` — Authentic textbook diagram objects (`media_id`, `caption`, `chunk_id`, `page_start`).
  - `event: follow_ups` — Contextual follow-up inquiry suggestions.
  - `event: done` — Generation complete marker with full synthesized reply.

### `GET /api/quota`
Returns daily request limit and remaining balance for the authenticated user/guest.
- **Response `200 OK`**:
  ```json
  {
    "limit": 50,
    "used": 3,
    "remaining": 47
  }
  ```

---

## 4. User Library & Ingestion Endpoints

### `GET /api/user/library`
Retrieves the user's personal curated library ("My Study Library") alongside the Global Catalog.
- **Response `200 OK`**:
  ```json
  {
    "library": [
      {
        "slug": "Harrison_2025_22nd_Edition",
        "title": "Harrison's Principles of Internal Medicine",
        "specialty": "Internal Medicine",
        "total_pages": 4273,
        "is_active": true
      }
    ],
    "global_catalog": [ ... ]
  }
  ```

### `POST /api/user/library/add`
Adds a textbook from the Global Catalog into the user's personal library.
- **Request Body (`application/json`)**: `{ "slug": "Harrison_2025_22nd_Edition" }`
- **Response `200 OK`**: `{ "success": true, "slug": "...", "total_active": 3 }`

### `POST /api/user/library/remove`
Removes a textbook from the user's personal library.
- **Request Body (`application/json`)**: `{ "slug": "Harrison_2025_22nd_Edition" }`
- **Response `200 OK`**: `{ "success": true, "slug": "...", "total_active": 2 }`

### `POST /api/user/library/toggle`
Toggles or explicitly sets the active consultation state for a textbook in the user's library.
- **Request Body (`application/json`)**: `{ "slug": "Harrison_2025_22nd_Edition", "is_active": false }`
- **Response `200 OK`**: `{ "success": true, "slug": "...", "total_active": 1 }`

### `POST /api/user/library/toggle-all`
Sets all textbooks in the user's personal library to active or inactive simultaneously.
- **Request Body (`application/json`)**: `{ "active": true }`
- **Response `200 OK`**: `{ "success": true, "active": true, "total_active": 4 }`

### `POST /api/books/upload`
Uploads a reference textbook PDF and initiates non-blocking background extraction and indexing.
- **Form Data (`multipart/form-data`)**:
  - `file`: PDF binary file
  - `title`: Textbook title string
  - `specialty`: Category or specialty string (default: `"General Medicine"`)
- **Response `202 Accepted`**:
  ```json
  {
    "job_id": "3c8a9942-8f1d-4e92-ba74-123456789abc",
    "title": "Harrison's Principles of Internal Medicine",
    "status": "pending",
    "message": "Upload accepted. Ingestion started in background."
  }
  ```

### `GET /api/books/ingestion/{job_id}`
Polls asynchronous ingestion progress and stage telemetry.
- **Response `200 OK`**:
  ```json
  {
    "job_id": "3c8a9942-...",
    "status": "running",
    "stage": "chunking",
    "progress_percent": 65,
    "message": "Extracted 4273 pages. Generating bounded semantic chunks...",
    "chunks_count": 16963,
    "user_error_message": null
  }
  ```

---

## 5. Content, Chunks & Authentic Diagrams

### `GET /api/books`
Returns the list of all indexed textbooks in the system with page counts and specialties.

### `GET /api/chunk/{chunk_id}`
Retrieves full passage text, heading path, and page boundaries for the interactive Evidence Drawer.
- **Response `200 OK`**:
  ```json
  {
    "chunk_id": "Williams_15e_ch16_s1165_c004",
    "book_slug": "Williams_Textbook_of_Endocrinology_15th_edition_2",
    "section_id": 1165,
    "page_start": 800,
    "page_end": 802,
    "heading_path": "Chapter 16: Contraception > Combined Oral Contraceptives > Adverse Effects",
    "text": "Venous thromboembolism (VTE) risk is substantially elevated in women older than 35 who smoke...",
    "content_type": "figure_caption"
  }
  ```

### `GET /api/figure/{chunk_id}/image`
Serves the high-resolution, column-aware cropped JPEG diagram plate directly from storage.
- **Response Header**: `Content-Type: image/jpeg`, `Cache-Control: public, max-age=86400`
- **Response `200 OK`**: Binary JPEG image.
- **Response `404 Not Found`**: Returned if no authentic visual plate exists on the page.

### `GET /api/session/{session_id}/citations`
Retrieves all accumulated verified citations across the conversation session.
