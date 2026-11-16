import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.db.groq_client import groq_wrapper
from app.db.weaviate_client import weaviate_wrapper
from app.db.neo4j_client import neo4j_wrapper
from app.services.representation import (
    embedding_service,
    extract_triples_with_groq,
    represent_and_store_chunks
)

client = TestClient(app)

def test_api_health():
    from app.main import health_check
    data = health_check()
    assert data["status"] == "healthy"
    assert "connectors" in data
    assert "groq" in data["connectors"]
    assert "vector_store" in data["connectors"]
    assert "graph_store" in data["connectors"]
    assert data["connectors"]["vector_store"]["connected"] is True
    assert data["connectors"]["graph_store"]["connected"] is True

def test_embedding_service():
    texts = [
        "Hybrid vector-graph retrieval enhances multimodal RAG.",
        "Deep neural representations encode semantic meaning."
    ]
    embeddings = embedding_service.encode(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 768
    assert len(embeddings[1]) == 768

def test_weaviate_vector_store():
    # Clear prior test entries
    weaviate_wrapper.clear()

    docs = [
        {
            "chunk_id": "test_c1",
            "source_id": "doc1",
            "modality": "document",
            "content": "Quantum computing enables superpolynomial speedups."
        },
        {
            "chunk_id": "test_c2",
            "source_id": "doc2",
            "modality": "document",
            "content": "Culinary arts and Italian pasta recipes."
        }
    ]
    embs = embedding_service.encode([d["content"] for d in docs])
    ids = weaviate_wrapper.add_documents(docs, embs)
    assert len(ids) == 2

    # Search quantum computing
    q_emb = embedding_service.encode_single("Quantum computational algorithms")
    results = weaviate_wrapper.search(q_emb, top_k=1)
    assert len(results) >= 1
    assert results[0]["chunk_id"] == "test_c1"
    assert results[0]["score"] > 0.0

def test_neo4j_graph_store():
    # Clear prior test entries
    neo4j_wrapper.clear()

    triples = [
        {"subject": "Project_Alpha", "predicate": "USES", "object": "Weaviate"},
        {"subject": "Project_Alpha", "predicate": "USES", "object": "Neo4j"},
        {"subject": "Weaviate", "predicate": "PROVIDES", "object": "Vector_Search"}
    ]
    neo4j_wrapper.add_triples(triples, source_id="test_src", chunk_id="test_chk_1", modality="document")

    # Query 2-hop neighborhood of Project_Alpha
    subgraph = neo4j_wrapper.query_neighborhood(["Project_Alpha"], hops=2)
    assert len(subgraph["nodes"]) >= 2
    assert len(subgraph["edges"]) >= 2

def test_triple_extraction():
    text = "Dr. Elena Vance introduced Project Alpha at the Zurich Conference in 2026."
    res = extract_triples_with_groq(text)
    assert "entities" in res
    assert "triples" in res
    assert len(res["entities"]) > 0 or len(res["triples"]) > 0

def test_representation_and_persistence(sample_pdf_file):
    from app.services.ingestion import ingest_document
    chunks = ingest_document(sample_pdf_file)
    assert len(chunks) > 0

    res = represent_and_store_chunks(chunks)
    assert res["chunks_stored"] == len(chunks)
    assert weaviate_wrapper.count() >= len(chunks)
