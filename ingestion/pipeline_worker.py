"""Background Ingestion Pipeline Worker for Dynamic Textbook Ingestion.

Executes end-to-end PDF processing in a non-blocking background thread:
1. Validates PDF integrity, page text layer, and encryption locks.
2. Extracts hierarchical Table of Contents (or builds fallback structure).
3. Extracts and sorts page text in reading order (multi-column aware).
4. Generates bounded semantic chunks (300-500 tokens).
5. Atomically commits sections and chunks into textbook_rag.db.
6. Maps failures to reassuring, high-level clinical error summaries.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from ingestion.chunk_sections import est_tokens, split_into_sentences
from ingestion.load_to_db import SqliteBackend
from storage.object_store import get_storage_provider

logger = logging.getLogger("ingestion.worker")

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "textbook_rag.db"
UPLOAD_STAGING_DIR = ROOT_DIR / "temp" / "uploads"
UPLOAD_STAGING_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Custom Exception Hierarchy
# =============================================================================

class IngestionError(Exception):
    """Base exception for all textbook ingestion pipeline failures."""
    pass


class EncryptedPdfError(IngestionError):
    """Raised when PDF is password protected or has publisher DRM restrictions."""
    pass


class ScannedPdfError(IngestionError):
    """Raised when PDF has no selectable digital text layer (scanned photocopies)."""
    pass


class CorruptedPdfError(IngestionError):
    """Raised when PDF stream is damaged, incomplete, or has 0 pages."""
    pass


class DuplicateBookError(IngestionError):
    """Raised when a book with the same title or slug already exists."""
    pass


# =============================================================================
# Error Classification
# =============================================================================

def classify_ingestion_error(exc: Exception) -> tuple[str, str]:
    """Translates raw exceptions into (user_friendly_summary, technical_traceback).

    Returns a high-level reassuring message explaining what happened and that the
    team has been logged with the report to investigate.
    """
    tech_details = traceback.format_exc()
    exc_str = str(exc).lower()

    if isinstance(exc, EncryptedPdfError) or "password" in exc_str or "encrypted" in exc_str:
        user_msg = (
            "This textbook is password-protected or restricted by publisher permissions. "
            "Please upload an unrestricted digital PDF."
        )
    elif isinstance(exc, ScannedPdfError):
        user_msg = (
            "This textbook appears to be a scanned document without an embedded digital text layer. "
            "Our technical team has been notified with this diagnostic report to work on OCR support. "
            "In the meantime, you can continue consultations with existing books or upload a digital-native copy."
        )
    elif (
        isinstance(exc, CorruptedPdfError)
        or "cannot open broken stream" in exc_str
        or "not a valid pdf" in exc_str
        or "empty file" in exc_str
    ):
        user_msg = (
            "The uploaded file is damaged, incomplete, or not a valid PDF document. "
            "Please verify the file on your device and try uploading again."
        )
    elif isinstance(exc, DuplicateBookError):
        user_msg = str(exc)
    else:
        user_msg = (
            "An unexpected formatting error occurred while reading the textbook sections. "
            "Our team has been notified with the diagnostic details and is working on a fix."
        )

    logger.error("Ingestion failed: %s\nTechnical Details:\n%s", exc, tech_details)
    return user_msg, tech_details


# =============================================================================
# Job Model and In-Memory Registry
# =============================================================================

@dataclass
class IngestionJob:
    job_id: str
    book_slug: str
    title: str
    specialty: str
    status: str = "queued"       # "queued", "running", "completed", "failed"
    stage: str = "queued"        # "validating", "toc", "extraction", "chunking", "indexing", "completed", "failed"
    progress_percent: int = 0
    message: str = "Job queued for background ingestion..."
    user_error_message: str | None = None
    technical_error: str | None = None
    total_pages: int = 0
    chunks_count: int = 0
    sections_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "book_slug": self.book_slug,
            "title": self.title,
            "specialty": self.specialty,
            "status": self.status,
            "stage": self.stage,
            "progress_percent": self.progress_percent,
            "message": self.message,
            "user_error_message": self.user_error_message,
            "technical_error": self.technical_error,
            "total_pages": self.total_pages,
            "chunks_count": self.chunks_count,
            "sections_count": self.sections_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


_JOBS: dict[str, IngestionJob] = {}
_JOBS_LOCK = threading.Lock()


def get_job(job_id: str) -> IngestionJob | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def create_job(job_id: str, title: str, specialty: str, book_slug: str) -> IngestionJob:
    with _JOBS_LOCK:
        job = IngestionJob(
            job_id=job_id,
            book_slug=book_slug,
            title=title,
            specialty=specialty,
            status="queued",
            stage="queued",
            progress_percent=0,
            message="Upload received. Queued for background ingestion...",
        )
        _JOBS[job_id] = job
        return job


def update_job(job_id: str, **kwargs) -> IngestionJob | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        for k, v in kwargs.items():
            if hasattr(job, k):
                setattr(job, k, v)
        job.updated_at = time.time()
        return job


# =============================================================================
# Helper Utilities
# =============================================================================

def generate_book_slug(title: str) -> str:
    """Generates a clean filesystem/DB-safe book slug from a title."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_")
    return clean or f"book_{int(time.time())}"


def check_book_exists(slug: str, title: str, db_path: Path | str | None = None) -> bool:
    """Checks whether a book slug or exact title already exists in textbook_rag.db."""
    target_db = Path(db_path) if db_path else DEFAULT_DB_PATH
    if not target_db.exists():
        return False
    try:
        conn = sqlite3.connect(str(target_db), timeout=5.0)
        cur = conn.cursor()
        res = cur.execute("SELECT slug, title FROM books;").fetchall()
        conn.close()

        def _norm(s: str) -> str:
            return re.sub(r"[^a-zA-Z0-9]+", "", s).lower()

        slug_norm = _norm(slug)
        title_norm = _norm(title)

        for b_slug, b_title in res:
            b_slug_norm = _norm(b_slug)
            b_title_norm = _norm(b_title)
            # Exact or normalized match
            if slug_norm == b_slug_norm or title_norm == b_title_norm:
                return True
            # Substring match if meaningful length (> 12 chars)
            if len(title_norm) > 12 and (title_norm in b_title_norm or b_title_norm in title_norm):
                return True
            if len(slug_norm) > 12 and (slug_norm in b_slug_norm or b_slug_norm in slug_norm):
                return True
        return False
    except Exception:
        return False


# =============================================================================
# Core Pipeline Execution
# =============================================================================

def _build_sections_from_toc(
    toc: list[list[Any]], total_pages: int, default_title: str
) -> list[dict[str, Any]]:
    """Converts PyMuPDF toc [[level, title, page], ...] into hierarchical sections."""
    if not toc:
        return [
            {
                "id": 1,
                "title": default_title,
                "level": 1,
                "parent_id": None,
                "pdf_start": 1,
                "pdf_end": total_pages,
                "heading_path": default_title,
                "is_leaf": True,
            }
        ]

    sections: list[dict[str, Any]] = []
    ancestor_stack: list[dict[str, Any]] = []

    for idx, item in enumerate(toc, start=1):
        level = int(item[0])
        raw_title = str(item[1]).strip() or f"Section {idx}"
        start_page = max(1, min(int(item[2]), total_pages))

        # Determine end_page from next TOC item
        if idx < len(toc):
            next_start = max(1, min(int(toc[idx][2]), total_pages))
            end_page = max(start_page, next_start - 1) if next_start > start_page else start_page
        else:
            end_page = total_pages

        # Find parent from ancestor stack
        while ancestor_stack and ancestor_stack[-1]["level"] >= level:
            ancestor_stack.pop()

        parent_id = ancestor_stack[-1]["id"] if ancestor_stack else None
        if ancestor_stack:
            heading_path = f"{ancestor_stack[-1]['heading_path']} > {raw_title}"
            # Parent is no longer a leaf
            ancestor_stack[-1]["is_leaf"] = False
        else:
            heading_path = raw_title

        sec_dict = {
            "id": idx,
            "title": raw_title,
            "level": level,
            "parent_id": parent_id,
            "pdf_start": start_page,
            "pdf_end": end_page,
            "heading_path": heading_path,
            "is_leaf": True,
        }
        sections.append(sec_dict)
        ancestor_stack.append(sec_dict)

    return sections


def _extract_page_text_blocks(doc: Any) -> list[dict[str, Any]]:
    """Extracts text per page, performing 2-column gutter sorting and noise pruning."""
    pages_data: list[dict[str, Any]] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        page_rect = page.rect
        page_height = page_rect.height

        # Prune running headers (top 35pt) and footers (bottom 35pt)
        blocks = page.get_text("blocks")
        filtered_blocks = []
        for b in blocks:
            # b = (x0, y0, x1, y1, text, block_no, block_type)
            if len(b) >= 5:
                y0, y1, btext = b[1], b[3], b[4]
                if y0 < 35 or y1 > (page_height - 35):
                    continue
                clean_btext = btext.strip()
                if clean_btext:
                    filtered_blocks.append((b[0], y0, b[2], y1, clean_btext))

        # Sort blocks: two-column check
        mid_x = page_rect.width / 2.0
        left_blocks = [b for b in filtered_blocks if b[2] <= (mid_x + 20)]
        right_blocks = [b for b in filtered_blocks if b[0] >= (mid_x - 20)]

        if len(left_blocks) >= 2 and len(right_blocks) >= 2 and (len(left_blocks) + len(right_blocks)) == len(filtered_blocks):
            # Two-column layout: left column top-to-bottom, then right column top-to-bottom
            left_blocks.sort(key=lambda b: b[1])
            right_blocks.sort(key=lambda b: b[1])
            sorted_blocks = left_blocks + right_blocks
        else:
            # Single-column: sort vertically by y0
            sorted_blocks = sorted(filtered_blocks, key=lambda b: b[1])

        combined_text = "\n\n".join(b[4] for b in sorted_blocks)
        pages_data.append({
            "page_num": page_num,
            "text": combined_text,
        })

    return pages_data


def _crop_figure_from_page(doc: Any, page_num: int, fig_caption: str) -> bytes | None:
    """Extracts high-resolution cropped diagram JPEG bytes from the PDF page."""
    if not doc:
        return None
    try:
        page_idx = max(0, min(page_num - 1, len(doc) - 1))
        page = doc[page_idx]

        match = re.search(r"\b(FIGURE\s+[\d\.]+[A-Za-z]?|Fig\.\s*[\d\.]+)\b", fig_caption, re.IGNORECASE)
        fig_token = match.group(1).strip() if match else None

        clip_rect = None
        if fig_token:
            rects = page.search_for(fig_token)
            if not rects:
                rects = page.search_for(fig_token.upper())
            if rects:
                r = rects[0]
                y_top = max(0, r.y0 - 450)
                y_bottom = min(page.rect.y1, r.y1 + 100)
                clip_rect = pymupdf.Rect(page.rect.x0, y_top, page.rect.x1, y_bottom)

        if clip_rect and clip_rect.height > 100:
            pix = page.get_pixmap(clip=clip_rect, dpi=130)
            return pix.tobytes("jpeg")

        embedded = page.get_images()
        for img_info in embedded:
            xref = img_info[0]
            w, h = img_info[2], img_info[3]
            if w >= 250 and h >= 180:
                extracted = doc.extract_image(xref)
                if extracted and extracted.get("image"):
                    return extracted["image"]

        pix = page.get_pixmap(dpi=120)
        return pix.tobytes("jpeg")
    except Exception as e:
        logger.debug("Figure extraction fallback for page %s: %s", page_num, e)
        return None


def _generate_chunks_from_sections(
    book_slug: str,
    sections: list[dict[str, Any]],
    pages_data: list[dict[str, Any]],
    target_tokens: int = 400,
    doc: Any | None = None,
) -> list[dict[str, Any]]:
    """Generates bounded semantic chunks (~300-500 tokens) with section breadcrumbs and figure images."""
    chunks: list[dict[str, Any]] = []
    if not sections or not pages_data:
        return chunks

    from collections import defaultdict
    store = get_storage_provider()

    sorted_secs = sorted(sections, key=lambda s: (s["pdf_start"], s["id"]))
    sec_lookup = {s["id"]: s for s in sorted_secs}
    sec_pages: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for p in pages_data:
        p_num = p["page_num"]
        active_sec = sorted_secs[0]
        for s in sorted_secs:
            if s["pdf_start"] <= p_num:
                active_sec = s
            else:
                break
        sec_pages[active_sec["id"]].append(p)

    chunk_seq = 1
    for sec_id, pages in sec_pages.items():
        sec = sec_lookup.get(sec_id)
        if not sec:
            continue

        full_sec_text = "\n\n".join(p["text"] for p in pages if p["text"].strip())
        if not full_sec_text.strip():
            continue

        min_page = min(p["page_num"] for p in pages)
        max_page = max(p["page_num"] for p in pages)

        sentences = split_into_sentences(full_sec_text)
        if not sentences:
            continue

        current_sentences: list[str] = []
        current_tokens = 0

        for sent in sentences:
            sent_tok = est_tokens(sent)
            if current_tokens + sent_tok > target_tokens and current_sentences:
                chunk_str = " ".join(current_sentences).strip()
                chunk_id = f"{book_slug}_s{sec_id:04d}_c{chunk_seq:04d}"
                c_hash = hashlib.sha256(f"{book_slug}:{chunk_id}:{chunk_str}".encode("utf-8")).hexdigest()
                
                is_fig = bool(re.search(r"\b(FIGURE|Fig\.)\s*[\d\.]+", chunk_str, re.IGNORECASE))
                c_type = "figure_caption" if is_fig else "prose"
                c_sub = "figure" if is_fig else "paragraph"

                chunks.append({
                    "chunk_id": chunk_id,
                    "section_id": sec_id,
                    "content_type": c_type,
                    "sub_type": c_sub,
                    "page_start": min_page,
                    "page_end": max_page,
                    "token_count": current_tokens,
                    "text": chunk_str,
                    "embed_text": f"[{sec['heading_path']}] {chunk_str}",
                    "content_hash": c_hash,
                })

                if is_fig and doc:
                    fig_bytes = _crop_figure_from_page(doc, min_page, chunk_str)
                    if fig_bytes:
                        try:
                            store.save_figure(book_slug, chunk_id, fig_bytes)
                        except Exception as e:
                            logger.debug("Failed to store figure image %s: %s", chunk_id, e)

                chunk_seq += 1
                current_sentences = [current_sentences[-1], sent]
                current_tokens = est_tokens(current_sentences[0]) + sent_tok
            else:
                current_sentences.append(sent)
                current_tokens += sent_tok

        if current_sentences:
            chunk_str = " ".join(current_sentences).strip()
            chunk_id = f"{book_slug}_s{sec_id:04d}_c{chunk_seq:04d}"
            c_hash = hashlib.sha256(f"{book_slug}:{chunk_id}:{chunk_str}".encode("utf-8")).hexdigest()
            
            is_fig = bool(re.search(r"\b(FIGURE|Fig\.)\s*[\d\.]+", chunk_str, re.IGNORECASE))
            c_type = "figure_caption" if is_fig else "prose"
            c_sub = "figure" if is_fig else "paragraph"

            chunks.append({
                "chunk_id": chunk_id,
                "section_id": sec_id,
                "content_type": c_type,
                "sub_type": c_sub,
                "page_start": min_page,
                "page_end": max_page,
                "token_count": current_tokens,
                "text": chunk_str,
                "embed_text": f"[{sec['heading_path']}] {chunk_str}",
                "content_hash": c_hash,
            })

            if is_fig and doc:
                fig_bytes = _crop_figure_from_page(doc, min_page, chunk_str)
                if fig_bytes:
                    try:
                        store.save_figure(book_slug, chunk_id, fig_bytes)
                    except Exception as e:
                        logger.debug("Failed to store figure image %s: %s", chunk_id, e)

            chunk_seq += 1

    return chunks


def run_ingestion_pipeline(
    job_id: str,
    pdf_path: Path | str,
    title: str,
    specialty: str,
    db_path: Path | str | None = None,
    book_slug: str | None = None,
) -> IngestionJob:
    """Executes the complete asynchronous ingestion workflow for an uploaded textbook."""
    pdf_file = Path(pdf_path)
    target_db = Path(db_path) if db_path else DEFAULT_DB_PATH
    doc = None

    try:
        current_job = get_job(job_id)
        resolved_slug = book_slug or (current_job.book_slug if current_job and current_job.book_slug else None) or generate_book_slug(title)
        # Stage 0: Validation
        update_job(
            job_id,
            status="running",
            stage="validating",
            progress_percent=5,
            message="Validating PDF integrity and digital text layer...",
        )

        if not pdf_file.exists() or pdf_file.stat().st_size == 0:
            raise CorruptedPdfError("The uploaded PDF file is missing or empty.")

        try:
            doc = pymupdf.open(str(pdf_file))
        except Exception as e:
            raise CorruptedPdfError(f"Failed to open PDF stream: {e}")

        if doc.is_encrypted:
            raise EncryptedPdfError("The PDF document is password-protected or encrypted.")

        total_pages = len(doc)
        if total_pages == 0:
            raise CorruptedPdfError("The PDF contains 0 readable pages.")

        # Text layer density check on first sample pages
        sample_pages = min(total_pages, 8)
        sample_text_len = sum(len(doc[i].get_text("text").strip()) for i in range(sample_pages))
        if sample_text_len < 60:
            raise ScannedPdfError(
                "PDF contains insufficient selectable text (appears to be scanned images without OCR)."
            )

        update_job(
            job_id,
            total_pages=total_pages,
            progress_percent=15,
            stage="toc",
            message=f"PDF verified ({total_pages} pages). Extracting table of contents...",
        )

        # Stage 1: Table of Contents & Structure
        toc = doc.get_toc()
        sections = _build_sections_from_toc(toc, total_pages, default_title=title)
        update_job(
            job_id,
            sections_count=len(sections),
            progress_percent=30,
            stage="extraction",
            message=f"Structured {len(sections)} sections. Extracting text in reading order...",
        )

        # Stage 2: Page Text Extraction
        pages_data = _extract_page_text_blocks(doc)
        update_job(
            job_id,
            progress_percent=65,
            stage="chunking",
            message=f"Extracted {len(pages_data)} pages. Generating bounded semantic chunks...",
        )

        # Stage 3: Bounded Semantic Chunking
        book_slug = resolved_slug
        chunks = _generate_chunks_from_sections(book_slug, sections, pages_data, doc=doc)
        if not chunks:
            raise IngestionError("No text passages could be chunked from this textbook.")

        update_job(
            job_id,
            chunks_count=len(chunks),
            progress_percent=85,
            stage="indexing",
            message=f"Generated {len(chunks)} chunks. Indexing into database...",
        )

        # Stage 4: Database Atomic Transaction
        backend = SqliteBackend(str(target_db))
        backend.init_schema()
        backend.load_book(
            book_slug=book_slug,
            sections=sections,
            chunks=chunks,
            title=title,
            specialty=specialty,
        )

        # Stage 5: Completion
        job = update_job(
            job_id,
            status="completed",
            stage="completed",
            progress_percent=100,
            message="Textbook successfully indexed into Global Library and ready for consultations.",
            book_slug=book_slug,
        )
        logger.info("Successfully completed ingestion job %s for '%s' (%s chunks)", job_id, title, len(chunks))
        return job or get_job(job_id)

    except Exception as exc:
        user_msg, tech_msg = classify_ingestion_error(exc)
        job = update_job(
            job_id,
            status="failed",
            stage="failed",
            message=user_msg,
            user_error_message=user_msg,
            technical_error=tech_msg,
        )
        return job or get_job(job_id)

    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        # Clean up temporary uploaded PDF only if inside staging directory
        if pdf_file.exists() and (UPLOAD_STAGING_DIR in pdf_file.parents or "uploads" in str(pdf_file)):
            try:
                pdf_file.unlink()
            except Exception:
                pass
