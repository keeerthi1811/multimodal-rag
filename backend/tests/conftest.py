import sys
import math
import struct
import wave
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
import pymupdf as fitz

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

@pytest.fixture(scope="session")
def sample_pdf_file(tmp_path_factory) -> str:
    """Generates a multi-page test PDF document."""
    temp_dir = tmp_path_factory.mktemp("sample_data")
    pdf_path = temp_dir / "test_report.pdf"
    
    doc = fitz.open()
    # Page 1
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text(
        (50, 72),
        "Project Alpha Architecture Report\n\n"
        "Project Alpha employs a hybrid vector-graph architecture for knowledge retrieval.\n"
        "The system achieves 94.2% precision on benchmark datasets.\n"
        "Primary components include Weaviate vector database and Neo4j graph database.\n"
        "The retrieval pipeline was deployed on 2026-03-15.\n",
        fontsize=12
    )
    # Page 2
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text(
        (50, 72),
        "Evaluation Metrics and Conflict Analysis\n\n"
        "Experimental evaluations show query latency of 185ms.\n"
        "Cross-modal conflict detection identifies contradictory assertions across text and image.\n"
        "Lead researcher Dr. Elena Vance verified the experimental methodology.\n",
        fontsize=12
    )
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)

@pytest.fixture(scope="session")
def sample_txt_file(tmp_path_factory) -> str:
    """Generates a test plain text document."""
    temp_dir = tmp_path_factory.mktemp("sample_data")
    txt_path = temp_dir / "test_notes.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(
            "Executive Meeting Minutes:\n"
            "Project Alpha budget allocation is set at $1.2M for fiscal year 2026.\n"
            "System throughput is measured at 450 requests per second.\n"
        )
    return str(txt_path)

@pytest.fixture(scope="session")
def sample_image_file(tmp_path_factory) -> str:
    """Generates a test PNG image chart."""
    temp_dir = tmp_path_factory.mktemp("sample_data")
    img_path = temp_dir / "test_chart.png"
    img = Image.new("RGB", (400, 300), color=(240, 245, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 380, 280], outline=(40, 80, 160), width=3)
    draw.text((40, 40), "Performance Benchmark Chart: 94.2% Precision", fill=(10, 20, 60))
    img.save(str(img_path))
    return str(img_path)

@pytest.fixture(scope="session")
def sample_audio_file(tmp_path_factory) -> str:
    """Generates a valid 1-second PCM WAV audio file."""
    temp_dir = tmp_path_factory.mktemp("sample_data")
    wav_path = temp_dir / "test_speech.wav"
    sample_rate = 16000
    duration = 1.0  # seconds
    frequency = 440.0  # Hz

    with wave.open(str(wav_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        num_frames = int(sample_rate * duration)
        for i in range(num_frames):
            val = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
            data = struct.pack("<h", val)
            wav_file.writeframesraw(data)

    return str(wav_path)
