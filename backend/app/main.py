import os
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.db.groq_client import groq_wrapper
from app.db.weaviate_client import weaviate_wrapper
from app.db.neo4j_client import neo4j_wrapper
from app.services.ingestion import ingest_file
from app.services.representation import represent_and_store_chunks
from app.services.generator import generate_grounded_response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app.main")

app = FastAPI(
    title="Unified Multimodal RAG Framework",
    description="Multimodal Knowledge Augmentation Framework using Hybrid Vector-Graph Retrieval and Contextual Evidence Fusion",
    version="1.0.0"
)

# Enable CORS for React frontend (Vite defaults to localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    similarity_weight: float = 0.5
    graph_weight: float = 0.5
    enable_mmr: bool = True
    mmr_lambda: float = 0.7
    source_filter: Optional[str] = None

@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Exposes health and connectivity status of Groq, Weaviate, and Neo4j connectors."""
    vector_count = weaviate_wrapper.count()
    graph_data = neo4j_wrapper.get_all(limit=10)
    
    return {
        "status": "healthy",
        "framework": "Unified Multimodal Knowledge Augmentation Framework",
        "version": "1.0.0",
        "connectors": {
            "groq": {
                "configured": groq_wrapper.is_configured,
                "model": settings.groq_model,
                "vision_model": settings.groq_vision_model,
                "audio_model": settings.groq_audio_model,
                "mode": "live_api" if groq_wrapper.is_configured else "simulated_fallback"
            },
            "vector_store": {
                "connected": weaviate_wrapper.is_connected,
                "backend": "weaviate_cloud" if not weaviate_wrapper.is_fallback else "local_disk_persisted",
                "chunks_indexed": vector_count,
                "embedding_model": settings.embedding_model
            },
            "graph_store": {
                "connected": neo4j_wrapper.is_connected,
                "backend": "neo4j_native" if not neo4j_wrapper.is_fallback else "local_disk_persisted",
                "nodes_count": len(graph_data.get("nodes", [])),
                "edges_count": len(graph_data.get("edges", []))
            }
        }
    }

@app.post("/api/upload")
def upload_file(
    file: UploadFile = File(...),
    source_id: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """Uploads and ingests a multimodal file (PDF, TXT, PNG, JPG, MP3, WAV)."""
    t0 = time.time()
    sid = source_id or Path(file.filename).stem
    save_path = settings.uploads_dir / file.filename

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload file: {e}")

    try:
        # Ingest file into chunks
        chunks = ingest_file(str(save_path), source_id=sid)
        t_ingest = time.time()

        # Represent & persist (vector embeddings + KG triples)
        store_res = represent_and_store_chunks(chunks)
        t_total = time.time()

        return {
            "status": "success",
            "source_id": sid,
            "filename": file.filename,
            "modality": chunks[0]["modality"] if chunks else "unknown",
            "chunks_count": len(chunks),
            "triples_stored": store_res.get("triples_stored", 0),
            "ingestion_latency_ms": round((t_ingest - t0) * 1000, 2),
            "representation_latency_ms": round((t_total - t_ingest) * 1000, 2),
            "total_latency_ms": round((t_total - t0) * 1000, 2),
            "sample_chunks": chunks[:3]
        }
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/api/query")
def query_rag_pipeline(req: QueryRequest) -> Dict[str, Any]:
    """Executes the 7-stage hybrid retrieval, conflict detection, evidence graph, and grounded generation."""
    try:
        result = generate_grounded_response(
            query=req.query,
            top_k=req.top_k,
            similarity_weight=req.similarity_weight,
            graph_weight=req.graph_weight,
            enable_mmr=req.enable_mmr,
            mmr_lambda=req.mmr_lambda,
            source_filter=req.source_filter
        )
        return result
    except Exception as e:
        logger.error(f"Pipeline query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/evaluate")
def run_evaluation() -> Dict[str, Any]:
    """Runs automated evaluation and benchmarking suite across Vector-Only, Graph-Only, and Proposed Hybrid."""
    try:
        from evaluation.benchmark import run_evaluation_benchmark
        results = run_evaluation_benchmark(rate_limit_pause_sec=0.1)
        return results
    except Exception as e:
        logger.error(f"Evaluation benchmark execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")

@app.get("/api/metrics")
def get_latest_metrics() -> Dict[str, Any]:
    """Returns the latest evaluation and benchmarking metrics JSON."""
    metrics_path = Path(__file__).resolve().parent.parent.parent / "evaluation" / "results" / "latest_metrics.json"
    if metrics_path.exists():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading metrics file: {e}")
            raise HTTPException(status_code=500, detail="Could not read metrics.")
    
    # If not yet generated, run benchmark to generate it
    from evaluation.benchmark import run_evaluation_benchmark
    return run_evaluation_benchmark(rate_limit_pause_sec=0.1)

@app.get("/api/graph")
def get_graph_data(limit: int = 100) -> Dict[str, Any]:
    """Returns nodes and edges from the knowledge graph."""
    return neo4j_wrapper.get_all(limit=limit)

class ApiKeyRequest(BaseModel):
    api_key: str

@app.get("/api/settings")
def get_settings_status() -> Dict[str, Any]:
    """Returns current runtime settings and API configuration status."""
    return {
        "groq_configured": groq_wrapper.is_configured,
        "groq_model": settings.groq_model,
        "vision_model": settings.groq_vision_model,
        "audio_model": settings.groq_audio_model,
        "embedding_model": settings.embedding_model,
        "has_key": bool(settings.groq_api_key and not settings.groq_api_key.startswith("gsk_placeholder"))
    }

@app.post("/api/settings/api-key")
def update_api_key(req: ApiKeyRequest) -> Dict[str, Any]:
    """Dynamically updates the Groq API key in memory and in backend/.env."""
    clean_key = req.api_key.strip()
    is_ok = groq_wrapper.set_api_key(clean_key)
    
    env_file = Path(__file__).resolve().parent.parent / ".env"
    try:
        lines = []
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith("GROQ_API_KEY="):
                new_lines.append(f"GROQ_API_KEY={clean_key}\n")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.insert(0, f"GROQ_API_KEY={clean_key}\n")
            
        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.warning(f"Could not update .env file: {e}")

    return {
        "status": "success",
        "configured": is_ok,
        "message": "Groq API key activated successfully." if is_ok else "Key saved, simulated mode active."
    }

@app.get("/api/sources")
def list_sources() -> Dict[str, Any]:
    """Returns a list of all distinct ingested sources across vector store and uploads."""
    sources: Dict[str, Dict[str, Any]] = {}
    
    docs = getattr(weaviate_wrapper.local_store, "documents", {})
    for cid, doc in docs.items():
        sid = doc.get("source_id", "unknown")
        mod = doc.get("modality", "unknown")
        meta = doc.get("metadata", {})
        fname = meta.get("file_name", sid)
        if sid not in sources:
            sources[sid] = {
                "source_id": sid,
                "filename": fname,
                "modality": mod,
                "chunks_count": 0,
                "sample_content": doc.get("content", "")[:120] + "..." if len(doc.get("content", "")) > 120 else doc.get("content", "")
            }
        sources[sid]["chunks_count"] += 1

    for p in settings.uploads_dir.iterdir():
        if p.is_file():
            sid = p.stem
            if sid not in sources:
                ext = p.suffix.lower()
                mod = "document"
                if ext in [".png", ".jpg", ".jpeg", ".webp"]:
                    mod = "image"
                elif ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
                    mod = "video"
                elif ext in [".mp3", ".wav"]:
                    mod = "audio"
                sources[sid] = {
                    "source_id": sid,
                    "filename": p.name,
                    "modality": mod,
                    "chunks_count": 0,
                    "sample_content": f"Uploaded {mod} file ({p.stat().st_size} bytes)"
                }
            if "size_bytes" not in sources[sid]:
                sources[sid]["size_bytes"] = p.stat().st_size

    return {"sources": list(sources.values())}

@app.delete("/api/source/{source_id}")
def delete_source_endpoint(source_id: str) -> Dict[str, Any]:
    """Permanently deletes an individual uploaded source from Vectors, Graph, and Disk."""
    vec_deleted = weaviate_wrapper.delete_source(source_id)
    graph_deleted = neo4j_wrapper.delete_source(source_id)

    disk_deleted = False
    for p in settings.uploads_dir.iterdir():
        if p.stem == source_id or p.name == source_id:
            try:
                p.unlink()
                disk_deleted = True
            except Exception as e:
                logger.warning(f"Could not remove file {p}: {e}")

    return {
        "status": "success",
        "source_id": source_id,
        "vector_chunks_deleted": vec_deleted,
        "graph_elements_deleted": graph_deleted,
        "disk_file_deleted": disk_deleted,
        "message": f"Successfully deleted source '{source_id}'."
    }

@app.delete("/api/clear")
@app.delete("/api/sources")
def clear_all_data() -> Dict[str, Any]:
    """Resets vector store, knowledge graph, and cleans uploads directory."""
    weaviate_wrapper.clear()
    neo4j_wrapper.clear()
    for p in settings.uploads_dir.iterdir():
        if p.is_file():
            try:
                p.unlink()
            except Exception:
                pass
    return {"status": "success", "message": "All vector store, graph data, and uploaded files cleared."}
