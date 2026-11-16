import pytest
from app.services.ingestion import (
    ingest_document,
    ingest_audio,
    ingest_image,
    ingest_file,
    chunk_text
)

def test_chunk_text_overlap():
    sample_text = "Word " * 200  # ~1000 characters
    chunks = chunk_text(sample_text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    # Check that overlap exists
    for i in range(len(chunks) - 1):
        assert chunks[i]["end"] > chunks[i+1]["start"]

def test_pdf_ingestion(sample_pdf_file):
    chunks = ingest_document(sample_pdf_file, chunk_size=256, overlap=32)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert "chunk_id" in chunk
        assert chunk["modality"] == "document"
        assert chunk["page_num"] in [1, 2]
        assert len(chunk["content"].strip()) > 0
        assert "source_id" in chunk["metadata"]
        assert chunk["metadata"]["file_name"] == "test_report.pdf"

def test_txt_ingestion(sample_txt_file):
    chunks = ingest_document(sample_txt_file, chunk_size=100, overlap=20)
    assert len(chunks) >= 1
    first_chunk = chunks[0]
    assert first_chunk["modality"] == "document"
    assert "Project Alpha" in first_chunk["content"]
    assert first_chunk["page_num"] == 1

def test_audio_ingestion(sample_audio_file):
    chunks = ingest_audio(sample_audio_file)
    assert len(chunks) >= 1
    first_chunk = chunks[0]
    assert first_chunk["modality"] == "audio"
    assert "start_time" in first_chunk
    assert "end_time" in first_chunk
    assert first_chunk["end_time"] >= first_chunk["start_time"]
    assert len(first_chunk["content"]) > 0

def test_image_ingestion(sample_image_file):
    chunks = ingest_image(sample_image_file)
    assert len(chunks) == 1
    first_chunk = chunks[0]
    assert first_chunk["modality"] == "image"
    assert len(first_chunk["content"]) > 0
    assert first_chunk["metadata"]["width"] == 400
    assert first_chunk["metadata"]["height"] == 300

def test_universal_ingest_dispatcher(sample_pdf_file, sample_image_file, sample_audio_file, sample_txt_file):
    pdf_chunks = ingest_file(sample_pdf_file)
    assert pdf_chunks[0]["modality"] == "document"

    txt_chunks = ingest_file(sample_txt_file)
    assert txt_chunks[0]["modality"] == "document"

    img_chunks = ingest_file(sample_image_file)
    assert img_chunks[0]["modality"] == "image"

    aud_chunks = ingest_file(sample_audio_file)
    assert aud_chunks[0]["modality"] == "audio"
