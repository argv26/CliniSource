"""Unit tests for Parallel Figure Resolution Pipeline and Zero-Images-to-LLM Architecture."""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.orchestrator import AgentOrchestrator
from storage.object_store import LocalStorageProvider, S3StorageProvider, get_storage_provider


def test_local_storage_provider_crud(tmp_path: Path):
    """Validates LocalStorageProvider save, get, exists, and URL resolution."""
    provider = LocalStorageProvider(cache_dir=tmp_path)
    book_slug = "test_book"
    chunk_id = "test_chunk_001"
    sample_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"

    assert not provider.figure_exists(chunk_id)
    assert provider.get_figure_bytes(chunk_id) is None
    assert provider.get_figure_path(chunk_id) is None

    # Save
    stored_path = provider.save_figure(book_slug, chunk_id, sample_jpeg)
    assert Path(stored_path).exists()
    assert provider.figure_exists(chunk_id)
    assert provider.get_figure_bytes(chunk_id) == sample_jpeg
    assert provider.get_figure_path(chunk_id) == tmp_path / f"{chunk_id}.jpg"
    assert provider.get_figure_url(chunk_id) == f"/api/figure/{chunk_id}/image"


def test_s3_storage_provider_crud(tmp_path: Path):
    """Validates S3StorageProvider calls S3 API and maintains local cache."""
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        provider = S3StorageProvider(
            endpoint_url="http://localhost:9000",
            bucket_name="test-figures-bucket",
            access_key="minioadmin",
            secret_key="minioadmin",
            local_fallback_dir=tmp_path,
        )

        chunk_id = "chunk_s3_101"
        sample_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF_S3_TEST"

        # Save calls put_object and saves locally
        s3_uri = provider.save_figure("book_a", chunk_id, sample_jpeg)
        assert s3_uri == f"s3://test-figures-bucket/figures/{chunk_id}.jpg"
        mock_s3.put_object.assert_called_once_with(
            Bucket="test-figures-bucket",
            Key=f"figures/{chunk_id}.jpg",
            Body=sample_jpeg,
            ContentType="image/jpeg",
        )
        assert (tmp_path / f"{chunk_id}.jpg").read_bytes() == sample_jpeg

        # Cache hit returns local bytes without hitting S3 again
        mock_s3.get_object.reset_mock()
        cached_bytes = provider.get_figure_bytes(chunk_id)
        assert cached_bytes == sample_jpeg
        mock_s3.get_object.assert_not_called()

        # Cache miss fetches from S3
        missing_chunk = "chunk_s3_miss"
        mock_s3.get_object.return_value = {
            "Body": io.BytesIO(b"s3_remote_bytes")
        }
        fetched = provider.get_figure_bytes(missing_chunk)
        assert fetched == b"s3_remote_bytes"
        mock_s3.get_object.assert_called_once_with(
            Bucket="test-figures-bucket",
            Key=f"figures/{missing_chunk}.jpg",
        )


def test_zero_images_in_llm_contents(monkeypatch):
    """Verify that Gemini stream_turn receives ONLY text parts and zero image parts."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    mock_plan = MagicMock()
    mock_plan.to_dict.return_value = {"search_queries": ["corneal ulcer signs"]}
    mock_plan.search_queries = ["corneal ulcer signs"]

    mock_planner = MagicMock()
    mock_planner.plan.return_value = mock_plan

    orchestrator = AgentOrchestrator(planner=mock_planner)

    dummy_figures = [
        {
            "chunk_id": "fig_chk_1",
            "caption": "FIGURE 12-4 Slit lamp examination of corneal ulcer.",
            "page_start": 340,
            "book_title": "Cornea Management",
        }
    ]

    mock_retrieval = {
        "clean_query": "corneal ulcer signs",
        "chunks": [{"id": "chk_1", "text": "corneal ulcer signs", "book_title": "Cornea", "section_title": "Signs", "page_start": 10, "citation_id": 1}],
        "sections": [],
        "figures": dummy_figures,
    }

    with patch("agent.orchestrator._execute_parallel_retrieval", return_value=mock_retrieval), \
         patch("google.genai.Client") as mock_genai_client:

        mock_client_inst = MagicMock()
        mock_genai_client.return_value = mock_client_inst

        # Simulate stream chunk
        mock_stream_chunk = MagicMock()
        mock_stream_chunk.text = "Clinical management includes intensive fluoroquinolone drops."
        mock_client_inst.models.generate_content_stream.return_value = [mock_stream_chunk]

        events = list(orchestrator.stream_turn("session_zero_img", "How to treat corneal ulcer?"))

        # Inspect generate_content_stream call arguments
        assert mock_client_inst.models.generate_content_stream.called
        call_kwargs = mock_client_inst.models.generate_content_stream.call_args[1]
        contents = call_kwargs["contents"]

        # Every Content object must only have text parts
        for content in contents:
            for part in content.parts:
                assert hasattr(part, "text"), "Found a part without text attribute"
                assert not hasattr(part, "inline_data") or part.inline_data is None
                assert not hasattr(part, "file_data") or part.file_data is None


def test_figures_emitted_early_in_stream(monkeypatch):
    """Verify that figures event is emitted before the first token event."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    mock_plan = MagicMock()
    mock_plan.to_dict.return_value = {"search_queries": ["anterior segment"]}
    mock_plan.search_queries = ["anterior segment"]

    mock_planner = MagicMock()
    mock_planner.plan.return_value = mock_plan

    orchestrator = AgentOrchestrator(planner=mock_planner)

    dummy_figures = [
        {
            "chunk_id": "fig_early_1",
            "caption": "FIGURE 1-1 Anatomy of the anterior segment.",
            "page_start": 12,
            "book_title": "Ophthalmology Handbook",
        }
    ]

    mock_retrieval = {
        "clean_query": "anterior segment",
        "chunks": [{"id": "chk_2", "text": "Anterior chamber depth", "book_title": "Ophth", "section_title": "Anatomy", "page_start": 12, "citation_id": 1}],
        "sections": [],
        "figures": dummy_figures,
    }

    with patch("agent.orchestrator._execute_parallel_retrieval", return_value=mock_retrieval), \
         patch("google.genai.Client") as mock_genai_client:

        mock_client_inst = MagicMock()
        mock_genai_client.return_value = mock_client_inst

        mock_chunk = MagicMock()
        mock_chunk.text = "The anterior segment consists of cornea and iris."
        mock_client_inst.models.generate_content_stream.return_value = [mock_chunk]

        events = list(orchestrator.stream_turn("session_early_fig", "Describe the anterior segment"))

        event_names = [e["event"] for e in events]
        assert "figures" in event_names
        assert "token" in event_names

        figures_first_idx = event_names.index("figures")
        first_token_idx = event_names.index("token")

        assert figures_first_idx < first_token_idx, (
            f"figures event (index {figures_first_idx}) should appear before token event (index {first_token_idx})"
        )
