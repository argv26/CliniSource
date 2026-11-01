"""Tool definitions and dispatcher for LLM function calling in Universal Textbook RAG."""
from __future__ import annotations

from typing import Any

from retrieval.tools import (
    get_chunk,
    get_toc,
    read_section,
    search_chunks,
    search_figures,
    search_sections,
)

# Open-AI / Gemini compatible tool schemas for Universal Textbook RAG
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_textbook_structure",
            "description": "Inspect the hierarchical outline, table of contents, and headings of indexed textbooks (Chapters, Sections, Statutory Titles) by keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Topic, heading, chapter name, or legal doctrine to search in textbook hierarchy."
                    },
                    "book_slug": {
                        "type": "string",
                        "description": "Optional book identifier to restrict outline search to a single volume."
                    },
                    "allowed_books": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of book identifiers to restrict search scope."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of sections to return (default: 5)."
                    }
                },
                "required": ["keywords"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_relevant_chunks",
            "description": "Retrieve granular textbook passages, rules, definitions, and tables grounded in textbook evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific query term, clinical concept, statute, or formula."
                    },
                    "book_slug": {
                        "type": "string",
                        "description": "Optional book identifier to restrict search to a single volume."
                    },
                    "allowed_books": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of book identifiers to restrict search scope."
                    },
                    "section_id": {
                        "type": "integer",
                        "description": "Optional section ID to restrict search within that section."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of chunks to return (default: 6, up to 8)."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_media_and_tables",
            "description": "Retrieve authentic textbook diagrams, illustrations, algorithm plates, and tables along with their captions and semantic descriptions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword or concept describing the required diagram, table, or visual evidence."
                    },
                    "book_slug": {
                        "type": "string",
                        "description": "Optional book identifier."
                    },
                    "allowed_books": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of book identifiers to restrict scope."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of visual assets to return (default: 4)."
                    }
                },
                "required": ["query"]
            }
        }
    },
    # Backward-compatible tool aliases
    {
        "type": "function",
        "function": {
            "name": "search_chunks",
            "description": "Search granular textbook passages, tables, and callouts by keyword or concept.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific search term or concept."
                    },
                    "book_slug": {
                        "type": "string",
                        "description": "Optional book identifier."
                    },
                    "allowed_books": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of book identifiers."
                    },
                    "section_id": {
                        "type": "integer",
                        "description": "Optional section ID."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum chunks (default: 6)."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_sections",
            "description": "Search section and chapter headings by concept or condition.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Topic heading or concept."
                    },
                    "book_slug": {
                        "type": "string",
                        "description": "Optional book identifier."
                    },
                    "allowed_books": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of book identifiers."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum sections (default: 5)."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_section",
            "description": "Read an entire textbook subsection in reading order with its prose and tables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_slug": {
                        "type": "string",
                        "description": "Book slug identifier."
                    },
                    "section_id": {
                        "type": "integer",
                        "description": "The section ID to read."
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Token cap (default: 2500)."
                    }
                },
                "required": ["book_slug", "section_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_toc",
            "description": "Browse table of contents or child subsections under a chapter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_slug": {
                        "type": "string",
                        "description": "Book slug identifier."
                    },
                    "parent_id": {
                        "type": "integer",
                        "description": "Parent section ID, or omit for root chapters."
                    }
                },
                "required": ["book_slug"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_chunk",
            "description": "Inspect a single chunk by its exact ID to retrieve its full text and citation metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chunk_id": {
                        "type": "string",
                        "description": "Exact chunk ID."
                    }
                },
                "required": ["chunk_id"]
            }
        }
    }
]


def execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Executes a retrieval tool by name with arguments (with mapping for universal aliases)."""
    # Universal tool mappings
    if name == "get_textbook_structure":
        query = arguments.get("keywords") or arguments.get("query", "")
        book_slug = arguments.get("book_slug")
        allowed_books = arguments.get("allowed_books")
        limit = arguments.get("limit", 5)
        return search_sections(query=query, book_slug=book_slug, allowed_books=allowed_books, limit=limit)
    elif name == "get_relevant_chunks":
        return search_chunks(**arguments)
    elif name == "get_media_and_tables":
        return search_figures(**arguments)
    # Legacy tool direct invocations
    elif name == "search_chunks":
        return search_chunks(**arguments)
    elif name == "search_sections":
        return search_sections(**arguments)
    elif name == "read_section":
        return read_section(**arguments)
    elif name == "get_toc":
        return get_toc(**arguments)
    elif name == "get_chunk":
        return get_chunk(**arguments)
    elif name == "search_figures":
        return search_figures(**arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")
