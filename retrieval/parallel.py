"""Parallel retrieval executor for concurrent chunks, sections, and figures querying."""
from __future__ import annotations

import concurrent.futures
import re
import sqlite3
from pathlib import Path
from typing import Any

from retrieval.tools import search_chunks, search_figures, search_sections
from ui.diagrams import DB_PATH, get_figure_image_path, has_figure_image

COMMON_ACRONYM_MAP = {
    r"\bocp\b": "oral contraceptives",
    r"\bcoc\b": "combined oral contraceptives",
    r"\bdvt\b": "deep vein thrombosis",
    r"\bpe\b": "pulmonary embolism",
    r"\bdka\b": "diabetic ketoacidosis",
    r"\bmi\b": "myocardial infarction",
    r"\braas\b": "renin angiotensin aldosterone",
}

GENERIC_FIGURE_STOPWORDS = {
    "contraindications", "contraindication", "management", "treatment",
    "algorithm", "evaluation", "protocol", "overview", "definition",
    "definitions", "syndrome", "disorder", "disease", "guide", "guidelines",
    "clinical", "approach", "diagnosis", "features", "causes", "therapy",
    "review", "basics", "principles", "introduction", "summary"
}


def _expand_query(q: str) -> list[str]:
    """Expands clinical acronyms to full textbook nomenclature."""
    expanded = q
    for pattern, replacement in COMMON_ACRONYM_MAP.items():
        if re.search(pattern, q, re.IGNORECASE):
            expanded = re.sub(pattern, replacement, expanded, flags=re.IGNORECASE)
            break
    if expanded.lower() != q.lower():
        return [q, expanded]
    return [q]


def _execute_parallel_retrieval(
    query: str | list[str],
    book_slug: str | None = None,
    allowed_books: list[str] | None = None,
    chunk_limit: int = 6,
    section_limit: int = 2,
    figure_limit: int = 4,
) -> dict[str, Any]:
    """Executes chunk search, section search, and figure search concurrently in a thread pool.

    Supports either a single query string or a list of planned clinical queries.
    When multiple queries are provided, searches are run across the queries and
    results are deduplicated while preserving relevance ordering.
    """
    raw_queries: list[str] = []
    if isinstance(query, list):
        for q in query:
            if q and q.strip():
                clean = re.sub(r"[^\w\s-]", " ", q).strip()
                raw_queries.extend(_expand_query(clean))
    else:
        clean = re.sub(r"[^\w\s-]", " ", query).strip()
        raw_queries.extend(_expand_query(clean))

    # Deduplicate queries while preserving order
    queries: list[str] = []
    for q in raw_queries:
        if q and q not in queries:
            queries.append(q)
    if not queries:
        queries = [""]

    primary_query = queries[0]
    display_query = " | ".join(queries[:2]) if len(queries) > 1 else primary_query

    def _fetch_all_chunks() -> list[dict[str, Any]]:
        combined: list[dict[str, Any]] = []
        seen_ids = set()
        for q in queries:
            c_args: dict[str, Any] = {"query": q, "limit": chunk_limit}
            if book_slug:
                c_args["book_slug"] = book_slug
            if allowed_books is not None:
                c_args["allowed_books"] = allowed_books
            results = search_chunks(**c_args)
            for r in results:
                cid = r.get("chunk_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    combined.append(r)
                elif not cid:
                    combined.append(r)
        return combined[:chunk_limit]

    def _fetch_all_sections() -> list[dict[str, Any]]:
        combined: list[dict[str, Any]] = []
        seen_ids = set()
        for q in queries:
            s_args: dict[str, Any] = {"query": q, "limit": section_limit}
            if book_slug:
                s_args["book_slug"] = book_slug
            if allowed_books is not None:
                s_args["allowed_books"] = allowed_books
            results = search_sections(**s_args)
            for r in results:
                sid = r.get("section_id")
                if sid and sid not in seen_ids:
                    seen_ids.add(sid)
                    combined.append(r)
                elif not sid:
                    combined.append(r)
        return combined[:section_limit]

    def _fetch_all_figures() -> list[dict[str, Any]]:
        combined: list[dict[str, Any]] = []
        seen_ids = set()

        # Build search queries for figures: include both full queries and core topical queries with meta-words stripped
        fig_search_queries = list(queries)
        for q in queries:
            core_words = [
                w for w in re.findall(r"\b[a-zA-Z]{3,}\b", q)
                if w.lower() not in GENERIC_FIGURE_STOPWORDS
            ]
            if core_words:
                core_q = " ".join(core_words)
                if core_q and core_q not in fig_search_queries:
                    fig_search_queries.append(core_q)

        for q in fig_search_queries:
            f_args: dict[str, Any] = {"query": q, "limit": figure_limit}
            if book_slug:
                f_args["book_slug"] = book_slug
            if allowed_books is not None:
                f_args["allowed_books"] = allowed_books
            try:
                results = search_figures(**f_args)
            except Exception as e:
                print(f"[ParallelRetrieval] Figure search error for '{q}': {e}")
                results = []
            for r in results:
                cid = r.get("chunk_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    combined.append(r)
                elif not cid:
                    combined.append(r)
        return combined[:figure_limit * 2]

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_chunks = executor.submit(_fetch_all_chunks)
        f_sections = executor.submit(_fetch_all_sections)
        f_figures = executor.submit(_fetch_all_figures)

        chunks_res = f_chunks.result()
        sections_res = f_sections.result()
        candidate_figures = f_figures.result()

    # Co-retrieve section-linked figures from the top matching chunks and sections
    seen_fig_ids = {f.get("chunk_id") for f in candidate_figures if f.get("chunk_id")}
    section_targets: list[tuple[str, int]] = []
    for c in chunks_res[:4]:
        if c.get("book_slug") and c.get("section_id"):
            pair = (c["book_slug"], c["section_id"])
            if pair not in section_targets:
                section_targets.append(pair)
    for s in sections_res[:2]:
        if s.get("book_slug") and s.get("section_id"):
            pair = (s["book_slug"], s["section_id"])
            if pair not in section_targets:
                section_targets.append(pair)

    if DB_PATH.exists() and section_targets:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            for b_slug, sec_id in section_targets:
                rows = conn.execute(
                    "SELECT chunk_id, book_slug, section_id, content_type, page_start, page_end, token_count, text FROM chunks WHERE book_slug = ? AND section_id = ? AND content_type = 'figure_caption'",
                    (b_slug, sec_id)
                ).fetchall()
                for r in rows:
                    cid = r[0]
                    if cid not in seen_fig_ids:
                        seen_fig_ids.add(cid)
                        candidate_figures.insert(0, {
                            "chunk_id": r[0],
                            "book_slug": r[1],
                            "section_id": r[2],
                            "content_type": r[3],
                            "page_start": r[4],
                            "page_end": r[5],
                            "token_count": r[6],
                            "text": r[7],
                        })
            conn.close()
        except Exception as e:
            print(f"[ParallelRetrieval] Error querying section figures: {e}")

    # Filter candidate figures strictly:
    # 1. Existence: The authentic figure image MUST exist on disk (>= 5KB). If no image exists, DO NOT SHOW IT!
    # 2. Subject relevance: Discard figures that only matched generic stop-words without sharing any query topic.
    generic_stopwords = {
        "contraindications", "contraindication", "management", "treatment",
        "algorithm", "evaluation", "protocol", "overview", "definition",
        "definitions", "syndrome", "disorder", "disease", "guide", "guidelines",
        "clinical", "approach", "diagnosis", "features", "causes", "therapy",
        "review", "basics", "principles", "introduction", "summary"
    }
    ambiguous_short_terms = {
        "law", "sign", "test", "type", "part", "case", "care", "view",
        "rate", "unit", "line", "cell", "step", "role", "form", "mode", "term"
    }
    subject_terms = [
        w.lower()
        for w in re.findall(r"\b[a-zA-Z]{3,}\b", " ".join(queries))
        if w.lower() not in generic_stopwords
    ]

    verified_figures: list[dict[str, Any]] = []
    for f in candidate_figures:
        cid = f.get("chunk_id")
        if not cid:
            continue
        if not has_figure_image(cid):
            continue

        fig_text = (f.get("text") or "").lower()
        if subject_terms:
            matched_terms = [t for t in subject_terms if t in fig_text]
            if not matched_terms:
                continue
            # If multiple query terms exist, avoid false-positive on a single ambiguous short word (e.g. "law" or "type")
            if len(subject_terms) >= 2 and len(matched_terms) == 1:
                single_match = matched_terms[0]
                if single_match in ambiguous_short_terms or len(single_match) < 4:
                    continue

        verified_figures.append(f)
        if len(verified_figures) >= figure_limit:
            break

    return {
        "clean_query": display_query,
        "chunks": chunks_res,
        "sections": sections_res,
        "figures": verified_figures,
    }


# Public alias
execute_parallel_retrieval = _execute_parallel_retrieval
