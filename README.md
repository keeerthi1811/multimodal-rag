# Unified Multimodal Knowledge Augmentation Framework
### Hybrid Vector-Graph Retrieval and Contextual Evidence Fusion

A full-stack, enterprise-grade multimodal Retrieval-Augmented Generation (RAG) system that ingests PDFs/documents, images, and audio files, simultaneously represents knowledge as semantic vectors (**Weaviate**) and entity-relationship graphs (**Neo4j**), performs a 7-stage hybrid retrieval pipeline with cross-modal conflict detection, and generates grounded answers using the **Groq API**—paired with an interactive React UI featuring a Query-Centric Evidence Graph and an Evaluation Metrics Dashboard.

---

## Key Features & Architecture

```
                                  [ User Query ]
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
         [ Stage 1: Vector Search ]             [ Stage 1: KG Neighborhood ]
           Weaviate (BGE-base-en)                  Neo4j (1-2 Hop Cypher)
                    │                                         │
                    └────────────────────┬────────────────────┘
                                         ▼
                       [ Stage 2: Multi-Signal Scoring ]
                 (Semantic + Graph Proximity + Corroboration)
                                         │
                                         ▼
                          [ Stage 3: CrossEncoder Rerank ]
                               (BAAI/bge-reranker-base)
                                         │
                                         ▼
                            [ Stage 4: Custom MMR ]
                       (λ = 0.7 Cross-Modal Diversity)
                                         │
                                         ▼
                       [ Stage 5: Conflict Detection ]
                    (Groq Structured JSON Contradiction)
                                         │
                                         ▼
                   [ Stage 6: Evidence Graph Construction ]
                       (Query-Centric Subgraph JSON)
                                         │
                                         ▼
                   [ Stage 7: Contextual Evidence Fusion ]
                                         │
                                         ▼
                     [ Grounded Generation & Citations ]
                        (Groq Llama-3.3-70B-Versatile)
```

1. **Multimodal Ingestion:**
   - **Documents (`.pdf`, `.txt`):** Ingested via `PyMuPDF` (`fitz`), parsed page-by-page, and chunked with sliding window overlap (`chunk_size=512`, `overlap=64`).
   - **Images (`.png`, `.jpg`):** Analyzed via Groq Vision (`llama-3.2-11b-vision-preview`) & CLIP embeddings to extract visual descriptions, numbers, diagrams, and OCR.
   - **Audio (`.mp3`, `.wav`):** Transcribed via Groq Whisper (`whisper-large-v3-turbo`) with start/end millisecond timestamps.

2. **Dual Knowledge Representation:**
   - **Semantic Vectors:** Encoded via `BAAI/bge-base-en-v1.5` embeddings into Weaviate (with automatic local disk-persisted fallback).
   - **Knowledge Graph:** Extracted via Groq JSON mode into `(Subject)-[PREDICATE]->(Object)` triples persisted in Neo4j Desktop / AuraDB (`bolt://localhost:7687`) with automatic local graph store fallback.

3. **7-Stage Retrieval & Reasoning Pipeline:**
   - **Stage 1 (Hybrid Retrieval):** Semantic vector search + 1–2 hop entity neighborhood queries.
   - **Stage 2 (Multi-Signal Scoring):** Weighted scoring combining semantic similarity, graph hop proximity, cross-modal corroboration bonus, and source reliability.
   - **Stage 3 (Reranking):** Cross-encoder reranking via `BAAI/bge-reranker-base`.
   - **Stage 4 (MMR Diversity Selection):** Maximal Marginal Relevance ($\lambda = 0.7$) preventing redundancy and fostering cross-modal diversity.
   - **Stage 5 (Conflict Detection):** Groq structured JSON evaluation identifying contradictory figures, dates, or assertions across sources without arbitrary merging.
   - **Stage 6 (Query-Centric Evidence Graph):** Temporary in-memory subgraph of Query, Entities, and Evidence with `SUPPORTS`, `MENTIONS`, and `CONTRADICTS` edges.
   - **Stage 7 (Contextual Evidence Fusion):** Structured context synthesis for grounded generation with precise citations (`[DOC: ... p.1]`, `[IMG: ...]`, `[AUDIO: ... 10s-15s]`).

4. **Telemetry & Latency Profiling:**
   - Real-time instrumentation of `retrieval_ms`, `rerank_mmr_ms`, `conflict_graph_ms`, `llm_generation_ms`, and `total_query_ms`.

---

## Project Structure

```
multimodal_rag/
├── backend/
│   ├── app/
│   │   ├── config.py              # Pydantic Settings & environment config
│   │   ├── main.py                # FastAPI routes (/api/health, /api/upload, /api/query, etc.)
│   │   ├── db/
│   │   │   ├── groq_client.py     # Groq client wrapper with structured JSON support
│   │   │   ├── weaviate_client.py # Weaviate client with automatic local disk fallback
│   │   │   └── neo4j_client.py    # Neo4j driver with local disk graph store fallback
│   │   └── services/
│   │       ├── ingestion.py       # PyMuPDF, Whisper, Vision/CLIP ingestion
│   │       ├── representation.py  # BGE embeddings & Groq JSON triple extraction
│   │       ├── retrieval.py       # Hybrid retrieval, scoring, CrossEncoder rerank, MMR
│   │       ├── reasoning.py       # Conflict detection & Evidence Graph builder
│   │       └── generator.py       # Groq grounded answer generation with citations
│   ├── tests/
│   │   ├── conftest.py            # Test fixtures (PDF, TXT, PNG, WAV generator)
│   │   ├── test_connectors.py     # Phase 1 connector & representation tests
│   │   ├── test_ingestion.py      # Phase 1 multimodal ingestion tests
│   │   ├── test_pipeline.py       # Phase 2 hybrid retrieval, conflict & telemetry tests
│   │   └── test_evaluation.py     # Phase 3 benchmark metrics tests
│   ├── requirements.txt           # Pinned backend dependencies
│   ├── .env.example               # Environment template
│   └── .env                       # Local active environment
├── evaluation/
│   ├── generate_sample_data.py    # Realistic multimodal test data generator
│   ├── benchmark.py               # Comparative benchmark (Vector vs Graph vs Hybrid)
│   ├── sample_data/               # Generated PDF, PNG, WAV, and ground_truth.json
│   └── results/
│       └── latest_metrics.json    # Persisted evaluation benchmarks
├── frontend/                      # React 19 + Vite + Tailwind CSS Editorial UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx         # Navigation header & live health badges
│   │   │   ├── Uploader.jsx       # Drag-and-drop multimodal uploader
│   │   │   ├── ChatStudio.jsx     # Chat studio with grounded citations & conflict cards
│   │   │   ├── EvidenceGraph.jsx  # Interactive SVG Query-Centric Evidence Graph
│   │   │   ├── LatencyBar.jsx     # Stage latency visual breakdown
│   │   │   └── EvaluationDashboard.jsx # Live benchmark & interactive charts
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## Quickstart & Local Setup

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & npm
- (Optional) Native **Neo4j Desktop** or AuraDB (`bolt://localhost:7687`)
- (Optional) **Weaviate Cloud** URL & API key (automatic local disk-persisted fallback enabled by default)
- **Groq API Key**: Get a free key at [console.groq.com](https://console.groq.com/)

---

### Step 1: Environment & Virtual Environment Setup

```bash
# Clone or navigate to the repository
cd d:/multimodal_rag

# Create Python virtual environment (if not already created)
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux / macOS:
# source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

---

### Step 2: Configure Environment Variables

Edit `backend/.env` with your credentials:
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_VISION_MODEL=llama-3.2-11b-vision-preview
GROQ_AUDIO_MODEL=whisper-large-v3-turbo

# Neo4j (Optional - defaults to automatic local fallback if offline)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Weaviate (Optional - defaults to automatic local fallback if offline)
WEAVIATE_URL=
WEAVIATE_API_KEY=
USE_LOCAL_VECTOR_FALLBACK=true

# Embedding & Reranker Models
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-base
WHISPER_MODE=groq
```

---

### Step 3: Run Verification Test Suites (Gates 1, 2, 3)

Run the full automated Pytest test suite across all verification gates:
```bash
# Set PYTHONPATH and run Pytest
$env:PYTHONPATH="backend"  # PowerShell
pytest backend/tests -v
```

All 20 tests across connectors, ingestion, pipeline reasoning, conflict detection, telemetry, and metrics verification will execute and pass.

---

### Step 4: Run Automated Multimodal Benchmark (Phase 3)

Generate test multimodal files and execute the comparative evaluation:
```bash
# Generate sample data (PDF, PNG chart, WAV audio, ground truth)
python evaluation/generate_sample_data.py

# Run comparative benchmark across Vector-Only vs Graph-Only vs Proposed Hybrid
python evaluation/benchmark.py
```
Results will be saved to `evaluation/results/latest_metrics.json`.

---

### Step 5: Start the Backend Server

```bash
# In the repository root with venv activated:
$env:PYTHONPATH="backend"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The FastAPI backend will be available at:
- **API Base:** `http://127.0.0.1:8000`
- **Swagger Docs:** `http://127.0.0.1:8000/docs`
- **Health Check:** `http://127.0.0.1:8000/api/health`

---

### Step 6: Start the React Frontend (Phase 4)

In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
Open your browser at `http://localhost:5173` to explore:
1. **Multimodal Studio Tab:**
   - Drag and drop `.pdf`, `.png`, `.wav` files or click **"Load Benchmark Sample Data"**.
   - Ask questions in the query box or choose suggested test queries.
   - Inspect grounded answers with inline citations.
   - Review **Cross-Modal Conflict Alert Cards** highlighting contradictory claims between Document and Image.
   - Interact with the **Query-Centric Evidence Graph** side panel (zoom, pan, inspect nodes, highlight contradiction edges).
   - Review the real-time **Stage Latency Breakdown**.
2. **Evaluation & Metrics Dashboard Tab:**
   - Click **"Run Live Benchmark"** to trigger live evaluation.
   - Review KPI cards (`Recall@K`, `MRR`, `Conflict F1`, `Latency`).
   - Analyze the **Grouped Bar Chart** comparing Vector-Only vs. Graph-Only vs. Proposed Hybrid.
   - Inspect the **Conflict Detection Confusion Matrix** (TP, FP, FN, TN).
   - Inspect **Stage Latency Profiling** and **Ingestion Latency by Modality**.

---

## API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Connector health status (Groq, Weaviate, Neo4j) |
| `POST` | `/api/upload` | Ingests multimodal file (PDF, TXT, PNG, JPG, MP3, WAV) |
| `POST` | `/api/query` | Executes 7-stage hybrid retrieval, conflict fusion & generation |
| `GET` | `/api/graph` | Returns knowledge graph nodes and edges |
| `POST` | `/api/evaluate` | Runs the automated comparative evaluation benchmark |
| `GET` | `/api/metrics` | Retrieves the latest evaluation metrics JSON |
| `DELETE` | `/api/clear` | Clears vector store and knowledge graph data |

---

## License & Credits
Built with Google DeepMind engineering principles, Groq Python SDK, PyMuPDF, Weaviate, Neo4j, and React 19 + Vite.
