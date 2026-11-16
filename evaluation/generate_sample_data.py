import math
import struct
import wave
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pymupdf as fitz

EVAL_DIR = Path(__file__).resolve().parent
SAMPLE_DATA_DIR = EVAL_DIR / "sample_data"
RESULTS_DIR = EVAL_DIR / "results"

for d in [SAMPLE_DATA_DIR, RESULTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def generate_pdf_report(dest_path: Path):
    """Generates a realistic multi-page PDF report with technical specifications."""
    doc = fitz.open()

    # Page 1: Overview & Budget
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text(
        (50, 60),
        "PROJECT ALPHA: 2026 ARCHITECTURE & OPERATIONS REPORT\n"
        "Lead Investigator: Dr. Elena Vance | Zurich Research Lab\n"
        "Date of Publication: 2026-03-15\n"
        "----------------------------------------------------------------------\n\n"
        "1. Executive Summary\n"
        "Project Alpha establishes a state-of-the-art multimodal knowledge augmentation\n"
        "framework uniting Weaviate vector embeddings and Neo4j graph reasoning.\n\n"
        "2. Financial Allocation\n"
        "The approved operating fiscal budget for Project Alpha is set at $1,200,000 ($1.2M)\n"
        "for the complete 2026 fiscal cycle, allocated primarily to GPU compute and cloud infrastructure.\n\n"
        "3. System Architecture\n"
        "The pipeline ingests heterogeneous documents, high-resolution imagery, and speech audio.\n"
        "Cross-modal alignment fuses semantic vectors with knowledge graph entity paths.\n",
        fontsize=11
    )

    # Page 2: Benchmark Performance & Metrics
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text(
        (50, 60),
        "4. Empirical Performance Benchmarks\n"
        "Experimental evaluations across 10,000 multimodal queries demonstrate:\n"
        "- Multimodal Retrieval Precision: 94.2% across text and image benchmarks.\n"
        "- Mean Query Latency: 185ms end-to-end execution.\n"
        "- Target Operational Throughput: 450 requests per second under peak load.\n\n"
        "5. Verification & Grounding Protocols\n"
        "All model outputs require strict inline citations traceable to source files.\n"
        "Cross-modal conflict detection flags contradictory claims across modalities.\n",
        fontsize=11
    )

    doc.save(str(dest_path))
    doc.close()
    print(f"Generated PDF: {dest_path}")

def generate_financial_infographic(dest_path: Path):
    """Generates a PNG financial infographic containing corroborations and an intentional numeric conflict."""
    img = Image.new("RGB", (700, 500), color=(248, 250, 252))
    draw = ImageDraw.Draw(img)

    # Outer border and banner
    draw.rectangle([15, 15, 685, 485], outline=(30, 64, 175), width=3)
    draw.rectangle([15, 15, 685, 75], fill=(30, 64, 175))
    draw.text((30, 30), "PROJECT ALPHA: 2026 FINANCIAL & METRICS INFOGRAPHIC", fill=(255, 255, 255))

    # Metric Card 1: Intentional Contradiction (Budget: $800K vs PDF $1.2M)
    draw.rectangle([40, 100, 330, 240], fill=(254, 242, 242), outline=(220, 38, 38), width=2)
    draw.text((55, 115), "APPROVED ANNUAL BUDGET", fill=(153, 27, 27))
    draw.text((55, 145), "$800,000 ($800K)", fill=(220, 38, 38))
    draw.text((55, 185), "Status: Approved by Finance Board (Q1)", fill=(100, 116, 139))

    # Metric Card 2: Corroboration (Precision: 94.2%)
    draw.rectangle([370, 100, 660, 240], fill=(240, 253, 244), outline=(22, 163, 74), width=2)
    draw.text((385, 115), "BENCHMARK PRECISION", fill=(21, 128, 61))
    draw.text((385, 145), "94.2% Precision", fill=(22, 163, 74))
    draw.text((385, 185), "Status: Verified by Zurich AI Labs", fill=(100, 116, 139))

    # Summary table
    draw.rectangle([40, 270, 660, 450], fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    draw.text((55, 285), "KEY METRIC COMPARISON TABLE:", fill=(15, 23, 42))
    draw.text((55, 320), "Throughput Capacity: 450 QPS (Queries per second)", fill=(51, 65, 85))
    draw.text((55, 350), "Average Response Latency: 185ms (P95 Latency: 240ms)", fill=(51, 65, 85))
    draw.text((55, 380), "Primary Infrastructure: Weaviate Vector Store & Neo4j KG", fill=(51, 65, 85))

    img.save(str(dest_path))
    # Write companion OCR/metadata text file for fallback/offline extraction
    txt_path = dest_path.with_suffix(".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(
            "PROJECT ALPHA: 2026 FINANCIAL & METRICS INFOGRAPHIC.\n"
            "APPROVED ANNUAL BUDGET: $800,000 ($800K) - Status: Approved by Finance Board (Q1).\n"
            "BENCHMARK PRECISION: 94.2% Precision - Status: Verified by Zurich AI Labs.\n"
            "Throughput Capacity: 450 QPS (Queries per second).\n"
            "Average Response Latency: 185ms (P95 Latency: 240ms).\n"
            "Primary Infrastructure: Weaviate Vector Store & Neo4j KG.\n"
        )
    print(f"Generated Image: {dest_path}")

def generate_standup_audio(dest_path: Path):
    """Generates a 3-second PCM WAV file with audio tone for ingestion."""
    sample_rate = 16000
    duration = 3.0
    frequency = 440.0

    with wave.open(str(dest_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        num_frames = int(sample_rate * duration)
        for i in range(num_frames):
            val = int(32767.0 * 0.4 * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
            data = struct.pack("<h", val)
            wav_file.writeframesraw(data)

    # Write companion transcript JSON for audio
    json_path = dest_path.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "text": "Dr. Elena Vance standup meeting. Project Alpha benchmark precision reached 94.2%. System architecture unites Weaviate vector indexing and Neo4j graph reasoning.",
            "duration": duration,
            "segments": [
                {"id": 0, "start": 0.0, "end": 1.0, "text": "Dr. Elena Vance standup meeting."},
                {"id": 1, "start": 1.0, "end": 2.0, "text": "Project Alpha benchmark precision reached 94.2%."},
                {"id": 2, "start": 2.0, "end": 3.0, "text": "System architecture unites Weaviate vector indexing and Neo4j graph reasoning."}
            ]
        }, f, indent=2)
    print(f"Generated Audio: {dest_path}")

def generate_ground_truth(dest_path: Path):
    """Saves ground truth test suite queries with expected retrieval targets and conflict pairs."""
    dataset = {
        "benchmark_name": "Multimodal Hybrid Vector-Graph Evaluation Suite",
        "version": "1.0.0",
        "description": "Ground truth evaluation dataset testing retrieval precision, recall, MRR, and cross-modal conflict detection across PDF, Image, and Audio.",
        "test_cases": [
            {
                "id": "TC_01",
                "query": "What is the approved fiscal budget for Project Alpha in 2026?",
                "target_keywords": ["budget", "$1,200,000", "$1.2M", "$800,000", "$800K"],
                "relevant_sources": ["alpha_annual_report", "alpha_financial_infographic"],
                "has_conflict": True,
                "expected_conflicts": [
                    {
                        "source_a": "alpha_annual_report",
                        "source_b": "alpha_financial_infographic",
                        "nature": "numeric_mismatch",
                        "claim_a": "$1,200,000 ($1.2M)",
                        "claim_b": "$800,000 ($800K)"
                    }
                ]
            },
            {
                "id": "TC_02",
                "query": "What retrieval precision and query latency was achieved by Project Alpha?",
                "target_keywords": ["94.2%", "precision", "185ms", "latency"],
                "relevant_sources": ["alpha_annual_report", "alpha_financial_infographic"],
                "has_conflict": False,
                "expected_conflicts": []
            },
            {
                "id": "TC_03",
                "query": "Who is the lead investigator and where is Project Alpha located?",
                "target_keywords": ["Elena Vance", "Zurich", "Lead Investigator"],
                "relevant_sources": ["alpha_annual_report"],
                "has_conflict": False,
                "expected_conflicts": []
            },
            {
                "id": "TC_04",
                "query": "What are the core database technologies used in the system architecture?",
                "target_keywords": ["Weaviate", "Neo4j", "vector", "graph"],
                "relevant_sources": ["alpha_annual_report", "alpha_financial_infographic"],
                "has_conflict": False,
                "expected_conflicts": []
            }
        ]
    }

    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    print(f"Generated Ground Truth: {dest_path}")

def generate_all():
    pdf_path = SAMPLE_DATA_DIR / "alpha_annual_report.pdf"
    img_path = SAMPLE_DATA_DIR / "alpha_financial_infographic.png"
    aud_path = SAMPLE_DATA_DIR / "alpha_standup_recording.wav"
    gt_path = SAMPLE_DATA_DIR / "ground_truth.json"

    generate_pdf_report(pdf_path)
    generate_financial_infographic(img_path)
    generate_standup_audio(aud_path)
    generate_ground_truth(gt_path)

if __name__ == "__main__":
    generate_all()
