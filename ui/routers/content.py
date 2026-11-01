"""Content, textbooks, chunks, figures, and bibliography citation endpoints."""
from __future__ import annotations

import re
import shutil
import uuid
from typing import Any
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ingestion.pipeline_worker import (
    UPLOAD_STAGING_DIR,
    check_book_exists,
    create_job,
    generate_book_slug,
    get_job,
    run_ingestion_pipeline,
)
from retrieval.tools import get_chunk, list_books
from ui.dependencies import get_orchestrator, resolve_or_create_user
from ui.diagrams import get_figure_image_path
from ui.library import (
    add_to_user_library,
    get_global_catalog,
    get_user_library,
    remove_from_user_library,
    set_all_user_books_active,
    toggle_user_book_active,
)
from ui.sessions import get_session_messages

router = APIRouter(prefix="/api", tags=["content"])


class BookActionRequest(BaseModel):
    slug: str


class BookToggleRequest(BaseModel):
    slug: str
    is_active: bool | None = None


class BookToggleAllRequest(BaseModel):
    active: bool = True


@router.get("/books")
def api_list_books():
    """Retrieve all available indexed textbooks and page statistics."""
    try:
        books = list_books()
        return {"books": books}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/library")
def api_get_user_library(request: Request, response: Response):
    """Retrieve the user's personal curated library and the global textbook catalog."""
    user = resolve_or_create_user(request, response)
    user_id = user["id"]
    library = get_user_library(user_id)
    catalog = get_global_catalog()

    library_slugs = {b["slug"] for b in library}
    global_items = []
    for book in catalog:
        global_items.append({
            **book,
            "in_user_library": book["slug"] in library_slugs,
            "is_active": any(b["slug"] == book["slug"] and b["is_active"] for b in library),
        })

    total_active = sum(1 for b in library if b.get("is_active"))
    return {
        "user_id": user_id,
        "library": library,
        "global_catalog": global_items,
        "total_active": total_active,
        "total_library": len(library),
        "total_global": len(catalog),
    }


@router.post("/user/library/add")
def api_add_user_library(req: BookActionRequest, request: Request, response: Response):
    """Add a textbook from the global catalog into the user's personal library."""
    user = resolve_or_create_user(request, response)
    user_id = user["id"]
    add_to_user_library(user_id, req.slug, is_active=True)
    library = get_user_library(user_id)
    total_active = sum(1 for b in library if b.get("is_active"))
    return {
        "success": True,
        "slug": req.slug,
        "library": library,
        "total_active": total_active,
    }


@router.post("/user/library/remove")
def api_remove_user_library(req: BookActionRequest, request: Request, response: Response):
    """Remove a textbook from the user's personal library."""
    user = resolve_or_create_user(request, response)
    user_id = user["id"]
    remove_from_user_library(user_id, req.slug)
    library = get_user_library(user_id)
    total_active = sum(1 for b in library if b.get("is_active"))
    return {
        "success": True,
        "slug": req.slug,
        "library": library,
        "total_active": total_active,
    }


@router.post("/user/library/toggle")
def api_toggle_user_book(req: BookToggleRequest, request: Request, response: Response):
    """Toggle active consultation state for a textbook in the user's library."""
    user = resolve_or_create_user(request, response)
    user_id = user["id"]
    toggle_user_book_active(user_id, req.slug, req.is_active)
    library = get_user_library(user_id)
    total_active = sum(1 for b in library if b.get("is_active"))
    return {
        "success": True,
        "slug": req.slug,
        "library": library,
        "total_active": total_active,
    }


@router.post("/user/library/toggle-all")
def api_toggle_all_user_books(req: BookToggleAllRequest, request: Request, response: Response):
    """Set all textbooks in the user's library to active or inactive."""
    user = resolve_or_create_user(request, response)
    user_id = user["id"]
    set_all_user_books_active(user_id, req.active)
    library = get_user_library(user_id)
    total_active = sum(1 for b in library if b.get("is_active"))
    return {
        "success": True,
        "active": req.active,
        "library": library,
        "total_active": total_active,
    }


@router.get("/chunk/{chunk_id}")
def api_get_chunk(chunk_id: str):
    """Fetch raw chunk content and metadata for the interactive Evidence Drawer."""
    data = get_chunk(chunk_id)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    if "text" in data and isinstance(data["text"], str):
        data["text"] = re.sub(r"(\b\w+)-\s*\n\s*(\w+\b)", r"\1\2", data["text"])
    return data


@router.get("/figure/{chunk_id}/image")
def api_get_figure_image(chunk_id: str):
    """Serve high-resolution textbook figure or diagram image."""
    img_path = get_figure_image_path(chunk_id)
    if not img_path or not img_path.exists():
        raise HTTPException(status_code=404, detail="Figure image not available for this chunk")
    return FileResponse(
        str(img_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/session/{session_id}/citations")
def api_get_session_citations(session_id: str, request: Request, response: Response):
    """Fetch all accumulated verified citations for a multi-turn conversation session."""
    user = resolve_or_create_user(request, response)
    orchestrator = get_orchestrator()
    session = orchestrator.context_manager.store.get_session(session_id)
    if session and session.citations:
        return {
            "session_id": session_id,
            "citations": [c.to_dict() for c in session.citations.values()]
        }

    # Fallback to database
    messages = get_session_messages(session_id, user["id"]) or []
    citations_map = {}
    for m in messages:
        for c in m.get("citations", []):
            citations_map[str(c["citation_id"])] = c

    return {
        "session_id": session_id,
        "citations": list(citations_map.values())
    }


@router.post("/books/upload", status_code=202)
async def api_upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    specialty: str = Form("General Medicine"),
):
    """Uploads a textbook PDF and starts background extraction and indexing."""
    clean_title = title.strip()
    clean_specialty = specialty.strip() or "General Medicine"

    if not clean_title:
        raise HTTPException(status_code=400, detail="Textbook title is required.")

    # Validate file extension
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are supported.")

    slug = generate_book_slug(clean_title)
    if check_book_exists(slug, clean_title):
        raise HTTPException(
            status_code=409,
            detail=f"A textbook with the title '{clean_title}' or slug '{slug}' already exists in the Global Library.",
        )

    # Validate PDF magic bytes
    header = await file.read(1024)
    if not header.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid PDF file: Missing %PDF header bytes.")
    await file.seek(0)

    job_id = str(uuid.uuid4())
    staged_filename = f"{job_id}_{re.sub(r'[^a-zA-Z0-9._-]+', '_', filename)}"
    staged_path = UPLOAD_STAGING_DIR / staged_filename

    # Save to staging directory
    with open(staged_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    job = create_job(job_id=job_id, title=clean_title, specialty=clean_specialty, book_slug=slug)

    # Run in background task
    background_tasks.add_task(
        run_ingestion_pipeline,
        job_id=job_id,
        pdf_path=staged_path,
        title=clean_title,
        specialty=clean_specialty,
    )

    return {
        "job_id": job_id,
        "book_slug": slug,
        "title": clean_title,
        "specialty": clean_specialty,
        "status": "queued",
        "message": "Upload accepted. Background ingestion started.",
    }


@router.get("/books/ingestion/{job_id}")
def api_get_ingestion_status(job_id: str):
    """Returns the live status, stage, and progress of an ingestion job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingestion job '{job_id}' not found.")
    return job.to_dict()

