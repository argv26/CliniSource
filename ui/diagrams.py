"""
ui/diagrams.py

High-performance Medical Diagram Extraction & Caching Engine for CliniSource.
Extracts high-resolution visual figures, diagrams, and anatomical plates directly
from source textbook PDFs using PyMuPDF and universal column-aware plate bounding.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from storage.object_store import get_storage_provider

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "ui" / "static" / "figures_cache"
DB_PATH = (ROOT / "clinisource.db") if ((ROOT / "clinisource.db").exists() and (ROOT / "clinisource.db").stat().st_size > 0) else (ROOT / "textbook_rag.db")
BOOKS_DIR = ROOT / "ingestion" / "test-books"
PROFILES_DIR = ROOT / "ingestion" / "analysis-result"

# In-memory cache for PageMap instances
_PAGE_MAPS: dict[str, Any] = {}


def _get_page_map(book_slug: str):
    """Loads and caches PageMap for the given book slug if available."""
    if book_slug in _PAGE_MAPS:
        return _PAGE_MAPS[book_slug]

    profile_path = PROFILES_DIR / book_slug / "profile.json"
    if profile_path.exists():
        try:
            from ingestion.page_map import PageMap
            pm = PageMap.from_profile(profile_path)
            _PAGE_MAPS[book_slug] = pm
            return pm
        except Exception:
            pass
    _PAGE_MAPS[book_slug] = None
    return None


def _resolve_pdf_path(book_slug: str) -> Path | None:
    """Finds the source PDF on disk for a book slug."""
    search_dirs = [BOOKS_DIR, ROOT]
    candidates: list[Path] = []
    for d in search_dirs:
        if d.exists():
            candidates.extend(list(d.glob("*.pdf")))

    for p in candidates:
        stem_slug = p.stem.replace(" ", "_").replace("-", "_").lower()
        clean_target = book_slug.replace("-", "_").lower()
        if clean_target in stem_slug or stem_slug in clean_target:
            return p

    # Fallback to direct name matching
    clean_lower = book_slug.lower()
    if "anatomy" in clean_lower:
        for p in candidates:
            if "anatomy" in p.name.lower():
                return p
    if "endocrinology" in clean_lower or "williams" in clean_lower:
        for p in candidates:
            if "endocrinology" in p.name.lower() or "williams" in p.name.lower():
                return p
    if "harrison" in clean_lower:
        for p in candidates:
            if "harrison" in p.name.lower():
                return p
    if "cornea" in clean_lower:
        for p in candidates:
            if "cornea" in p.name.lower():
                return p

    return None


def extract_clean_figure_rect(page: Any, fig_token: str) -> Any | None:
    """Universal column-aware plate-bounding algorithm for medical textbook figures.

    Detects the visual plate (drawings, charts, or embedded raster images) and caption
    while strictly isolating multi-column layouts to exclude adjacent text columns.
    Returns None if no authentic visual diagram plate is present on the page.
    """
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            return None

    pw = page.rect.width
    ph = page.rect.height

    # 1. Identify Caption Block (must be an authentic caption heading, not an in-text parenthetical citation)
    blocks = page.get_text("blocks")
    caption_block = None

    token_clean = fig_token.strip()
    m = re.search(r"(\d+)\s*[\.\-]\s*(\d+[a-zA-Z]?)", token_clean)
    if m:
        num_pattern = rf"{m.group(1)}\s*[\.\-]\s*{m.group(2)}"
    else:
        num_pattern = re.escape(token_clean)

    pattern = re.compile(
        rf"(?:^|[•·■\-\*\n\r\t])\s*(?:FIG(?:URE)?\.?\s*){num_pattern}(?!\s*\))(?:\b|\s|[\.:\u2000-\u200b])",
        re.IGNORECASE,
    )

    for b in blocks:
        text = b[4]
        if pattern.search(text):
            caption_block = pymupdf.Rect(b[:4])
            break

    # If pattern didn't match directly, check for blocks starting with the figure token
    if not caption_block:
        for b in blocks:
            text = b[4].strip()
            if re.match(rf"^(?:[•·■\-\*]\s*)?(?:FIG(?:URE)?\.?\s*){num_pattern}", text, re.IGNORECASE):
                caption_block = pymupdf.Rect(b[:4])
                break

    if not caption_block:
        return None

    # 2. Determine Column Boundaries
    if caption_block.x1 <= 0.58 * pw and caption_block.width < 0.55 * pw:
        col_x0 = max(15.0, caption_block.x0 - 15.0)
        col_x1 = min(pw * 0.52, max(caption_block.x1 + 10.0, pw * 0.48))
        is_column = "LEFT"
    elif caption_block.x0 >= 0.42 * pw and caption_block.width < 0.55 * pw:
        col_x0 = max(pw * 0.48, min(caption_block.x0 - 10.0, pw * 0.52))
        col_x1 = min(pw - 15.0, caption_block.x1 + 15.0)
        is_column = "RIGHT"
    else:
        col_x0 = max(15.0, caption_block.x0 - 15.0)
        col_x1 = min(pw - 15.0, caption_block.x1 + 15.0)
        is_column = "FULL"

    # 3. Check for embedded raster images in this column / region
    matching_img_rect = None
    for img_info in page.get_images():
        xref = img_info[0]
        img_rect_list = page.get_image_rects(xref)
        for ir in img_rect_list:
            if ir.width < 40 or ir.height < 40:
                continue
            # Column horizontal boundary checks
            if is_column == "LEFT" and ir.x0 > col_x1:
                continue
            if is_column == "RIGHT" and ir.x1 < col_x0:
                continue

            overlap = min(ir.x1, col_x1) - max(ir.x0, col_x0)
            if overlap > 25 or (is_column == "FULL" and ir.width > 180):
                # Vertical proximity to caption (above within 500 pt, or below within 200 pt)
                dist_above = caption_block.y0 - ir.y1
                dist_below = ir.y0 - caption_block.y1
                if (-25 <= dist_above <= 500) or (-25 <= dist_below <= 200):
                    if matching_img_rect is None:
                        matching_img_rect = ir
                    else:
                        matching_img_rect = matching_img_rect | ir

    if matching_img_rect:
        final_rect = matching_img_rect | caption_block
        if is_column == "LEFT":
            return pymupdf.Rect(
                max(page.rect.x0, col_x0 - 6),
                max(page.rect.y0, final_rect.y0 - 6),
                min(pw * 0.52, final_rect.x1 + 6),
                min(page.rect.y1, final_rect.y1 + 6),
            )
        elif is_column == "RIGHT":
            return pymupdf.Rect(
                max(pw * 0.48, final_rect.x0 - 6),
                max(page.rect.y0, final_rect.y0 - 6),
                min(page.rect.x1, col_x1 + 6),
                min(page.rect.y1, final_rect.y1 + 6),
            )
        else:
            return pymupdf.Rect(
                max(page.rect.x0, final_rect.x0 - 6),
                max(page.rect.y0, final_rect.y0 - 6),
                min(page.rect.x1, final_rect.x1 + 6),
                min(page.rect.y1, final_rect.y1 + 6),
            )

    # 4. Check for vector drawings in this column (charts, graphs, clinical pathways)
    drawings = page.get_drawings()
    col_drawings = []
    for d in drawings:
        dr = d["rect"]
        if is_column == "LEFT" and dr.x1 > col_x1:
            continue
        if is_column == "RIGHT" and dr.x0 < col_x0:
            continue
        if dr.y0 < 38 or dr.y1 > ph - 30:
            continue
        # Proximity: drawing above caption (up to 480 pt)
        if 10 < caption_block.y0 - dr.y0 < 480 and dr.y1 <= caption_block.y0 + 25:
            col_drawings.append(dr)
        # Proximity: drawing below caption (up to 380 pt)
        elif 0 < dr.y0 - caption_block.y1 < 380 and dr.y0 >= caption_block.y1 - 15:
            col_drawings.append(dr)

    if col_drawings:
        draw_union = col_drawings[0]
        for dr in col_drawings[1:]:
            draw_union = draw_union | dr

        # Include text blocks strictly within the chart and column
        for b in blocks:
            br = pymupdf.Rect(b[:4])
            if is_column == "LEFT" and br.x1 > col_x1:
                continue
            if is_column == "RIGHT" and br.x0 < col_x0:
                continue
            if (draw_union.y0 - 15 <= br.y0 and br.y1 <= caption_block.y1 + 10) or \
               (caption_block.y0 - 10 <= br.y0 and br.y1 <= draw_union.y1 + 15):
                if br.y0 > 38 and br.y1 < ph - 30:
                    draw_union = draw_union | br

        final_rect = draw_union | caption_block
        if is_column == "LEFT":
            return pymupdf.Rect(
                max(page.rect.x0, col_x0 - 6),
                max(page.rect.y0, final_rect.y0 - 6),
                min(pw * 0.52, final_rect.x1 + 6),
                min(page.rect.y1, final_rect.y1 + 6),
            )
        elif is_column == "RIGHT":
            return pymupdf.Rect(
                max(pw * 0.48, final_rect.x0 - 6),
                max(page.rect.y0, final_rect.y0 - 6),
                min(page.rect.x1, col_x1 + 6),
                min(page.rect.y1, final_rect.y1 + 6),
            )
        else:
            return pymupdf.Rect(
                max(page.rect.x0, final_rect.x0 - 6),
                max(page.rect.y0, final_rect.y0 - 6),
                min(page.rect.x1, final_rect.x1 + 6),
                min(page.rect.y1, final_rect.y1 + 6),
            )

    # 5. Strictly reject: If neither raster image nor vector drawings exist,
    # DO NOT EMIT AN IMAGE. Zero random text fallbacks.
    return None


def has_figure_image(chunk_id: str) -> bool:
    """Fast check whether an authentic figure image exists on disk without triggering extraction."""
    target_cache_file = CACHE_DIR / f"{chunk_id}.jpg"
    if target_cache_file.exists() and target_cache_file.stat().st_size >= 5000:
        return True
    try:
        store = get_storage_provider()
        existing_path = store.get_figure_path(chunk_id)
        if existing_path and existing_path.exists() and existing_path.stat().st_size > 0:
            return True
    except Exception:
        pass
    return False


def get_figure_image_path(chunk_id: str) -> Path | None:
    """Resolves or extracts a cached JPEG image for a textbook figure chunk.

    Guarantees:
    - Tight cropping around visual diagrams/plates.
    - Zero bleed into adjacent columns.
    - Rejection (returns None) for chunks without visual plates (no random text).

    Args:
        chunk_id: The chunk identifier from the CliniSource database.

    Returns:
        Path to the cached image on disk, or None if extraction is unavailable.
    """
    store = get_storage_provider()
    existing_path = store.get_figure_path(chunk_id)
    if existing_path and existing_path.exists() and existing_path.stat().st_size > 0:
        return existing_path

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target_cache_file = CACHE_DIR / f"{chunk_id}.jpg"
    if target_cache_file.exists() and target_cache_file.stat().st_size >= 5000:
        return target_cache_file

    if not DB_PATH.exists():
        return None

    # Query chunk metadata from database
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT chunk_id, book_slug, page_start, text, content_type FROM chunks WHERE chunk_id = ?",
            (chunk_id,),
        ).fetchone()
        if not row:
            return None
        _, book_slug, page_start, raw_text, _ = row
    finally:
        conn.close()

    pdf_path = _resolve_pdf_path(book_slug)
    if not pdf_path or not pdf_path.exists():
        return None

    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            return None

    pdf_page_idx = max(0, int(page_start) - 1) if page_start else 0

    try:
        doc = pymupdf.open(str(pdf_path))
        if pdf_page_idx >= len(doc):
            pdf_page_idx = min(len(doc) - 1, max(0, pdf_page_idx))
        page = doc[pdf_page_idx]

        # Extract figure label token from text
        match = re.search(
            r"\b(FIGURE\s+[\d\.]+[A-Za-z]?|Fig\.\s*[\d\.]+|FIGURE\s+[\d\-]+[A-Za-z]?|Fig\.\s*[\d\-]+[A-Za-z]?)\b",
            raw_text,
            re.IGNORECASE,
        )
        if not match:
            doc.close()
            return None

        fig_token = match.group(1).strip()
        rect = extract_clean_figure_rect(page, fig_token)
        if not rect:
            doc.close()
            return None

        # Render high-resolution crisp crop (180 DPI)
        pix = page.get_pixmap(clip=rect, dpi=180)
        pix.save(str(target_cache_file), "jpeg", jpg_quality=92)
        doc.close()
        return target_cache_file

    except Exception as e:
        print(f"Failed to extract figure {chunk_id}: {e}")
        return None
