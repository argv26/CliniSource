"""Parallel retrieval executor for concurrent chunks, sections, and figures querying."""
from __future__ import annotations

import concurrent.futures
import re
from typing import Any

from retrieval.tools import search_chunks, search_figures, search_sections


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
    if isinstance(query, list):
        queries = [re.sub(r"[^\w\s-]", " ", q).strip() for q in query if q and q.strip()]
        if not queries:
            queries = [""]
    else:
        queries = [re.sub(r"[^\w\s-]", " ", query).strip()]

    primary_query = queries[0]
    display_query = " | ".join(queries) if len(queries) > 1 else primary_query

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
        for q in queries:
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
        return combined[:figure_limit]

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_chunks = executor.submit(_fetch_all_chunks)
        f_sections = executor.submit(_fetch_all_sections)
        f_figures = executor.submit(_fetch_all_figures)

        chunks_res = f_chunks.result()
        sections_res = f_sections.result()
        figures_res = f_figures.result()

    return {
        "clean_query": display_query,
        "chunks": chunks_res,
        "sections": sections_res,
        "figures": figures_res,
    }


# Public alias
execute_parallel_retrieval = _execute_parallel_retrieval
