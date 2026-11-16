import os
import pytest
from pathlib import Path
from app.db.weaviate_client import weaviate_wrapper
from app.db.neo4j_client import neo4j_wrapper
from app.db.groq_client import groq_wrapper
from app.services.ingestion import ingest_file, extract_ocr_from_image_or_array
from app.services.representation import represent_and_store_chunks

def test_delete_source():
    # 1. Insert test chunk
    test_chunk = {
        "chunk_id": "test_del_01",
        "source_id": "test_delete_doc",
        "modality": "document",
        "content": "This is temporary content for testing deletion.",
        "metadata": {"source_id": "test_delete_doc", "modality": "document"}
    }
    represent_and_store_chunks([test_chunk])

    # Verify present
    res = weaviate_wrapper.search([0.1]*768, top_k=5, filters={"source_id": "test_delete_doc"})
    assert any(c["source_id"] == "test_delete_doc" for c in res)

    # 2. Delete source
    deleted_vec = weaviate_wrapper.delete_source("test_delete_doc")
    assert deleted_vec >= 1

    deleted_graph = neo4j_wrapper.delete_source("test_delete_doc")
    assert isinstance(deleted_graph, int)

    # Verify removed
    res_after = weaviate_wrapper.search([0.1]*768, top_k=5, filters={"source_id": "test_delete_doc"})
    assert not any(c["source_id"] == "test_delete_doc" for c in res_after)

def test_settings_api_key_update():
    # Test updating API key
    is_ok = groq_wrapper.set_api_key("gsk_test_mock_key_12345")
    # Non-placeholder key should initialize or configure
    assert groq_wrapper.is_configured is True
    # Reset back to testing key
    groq_wrapper.set_api_key("gsk_placeholder_api_key_for_testing")
    assert groq_wrapper.is_configured is False

def test_extract_ocr():
    # Test on existing sample image
    sample_img = Path("backend/data/uploads/Screenshot 2026-10-14 211621.png")
    if sample_img.exists():
        ocr_text = extract_ocr_from_image_or_array(str(sample_img))
        assert len(ocr_text) > 0
        assert "Figure" in ocr_text or "Responsible" in ocr_text or "Innovation" in ocr_text or "RRI" in ocr_text
