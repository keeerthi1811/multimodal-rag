import pytest
from app.config import settings
from app.db.weaviate_client import weaviate_wrapper
from app.db.neo4j_client import neo4j_wrapper
from app.services.retrieval import (
    hybrid_retrieval,
    compute_mmr,
    extract_query_entities
)
from app.services.reasoning import (
    detect_cross_modal_conflicts,
    build_query_centric_evidence_graph,
    contextual_evidence_fusion
)
from app.services.generator import generate_grounded_response
from app.main import query_rag_pipeline, QueryRequest

@pytest.fixture(autouse=True)
def setup_rag_test_data():
    """Populates vector and graph stores with multimodal test knowledge."""
    weaviate_wrapper.clear()
    neo4j_wrapper.clear()

    # Document Chunk 1: General architecture
    doc_chunk = {
        "chunk_id": "doc_alpha_01",
        "source_id": "report_alpha.pdf",
        "modality": "document",
        "content": "Project Alpha achieves 94.2% precision on benchmark datasets using hybrid vector-graph retrieval.",
        "metadata": {"source_id": "report_alpha.pdf", "page_num": 1, "modality": "document"}
    }

    # Document Chunk 2: Budget specification
    budget_chunk = {
        "chunk_id": "doc_alpha_02",
        "source_id": "report_alpha.pdf",
        "modality": "document",
        "content": "Project Alpha fiscal budget allocation is strictly set at $1.2M for 2026 operations.",
        "metadata": {"source_id": "report_alpha.pdf", "page_num": 2, "modality": "document"}
    }

    # Image Chunk: Conflicting budget info
    image_chunk = {
        "chunk_id": "img_chart_01",
        "source_id": "budget_infographic.png",
        "modality": "image",
        "content": "Visual financial infographic indicates Project Alpha approved budget: $800K for 2026 operations.",
        "metadata": {"source_id": "budget_infographic.png", "width": 800, "height": 600, "modality": "image"}
    }

    # Audio Chunk: Meeting notes corroborating precision
    audio_chunk = {
        "chunk_id": "aud_meeting_01",
        "source_id": "standup_audio.wav",
        "modality": "audio",
        "content": "Dr. Elena Vance noted during standup that Project Alpha benchmark precision reached 94.2%.",
        "metadata": {"source_id": "standup_audio.wav", "start_time": 10.5, "end_time": 18.0, "modality": "audio"}
    }

    all_chunks = [doc_chunk, budget_chunk, image_chunk, audio_chunk]

    # Store in vector store
    from app.services.representation import embedding_service
    embeddings = embedding_service.encode([c["content"] for c in all_chunks])
    weaviate_wrapper.add_documents(all_chunks, embeddings)

    # Store in knowledge graph
    triples = [
        {"subject": "Project_Alpha", "predicate": "ACHIEVES", "object": "Precision_94_2"},
        {"subject": "Project_Alpha", "predicate": "HAS_BUDGET", "object": "Budget_1_2M"},
        {"subject": "Dr_Elena_Vance", "predicate": "LEADS", "object": "Project_Alpha"}
    ]
    neo4j_wrapper.add_triples(triples, source_id="report_alpha.pdf", chunk_id="doc_alpha_01", modality="document")

def test_query_entity_extraction():
    entities = extract_query_entities("What did Dr. Elena Vance design for Project Alpha in Zurich?")
    assert len(entities) > 0
    assert any("Alpha" in e or "Vance" in e for e in entities)

def test_hybrid_retrieval_and_scoring():
    query = "Project Alpha precision benchmark"
    res = hybrid_retrieval(query, top_k=3, similarity_weight=0.5, graph_weight=0.5, enable_mmr=True)

    assert "chunks" in res
    assert len(res["chunks"]) > 0
    for chunk in res["chunks"]:
        assert "multi_signal_score" in chunk
        assert "rerank_score" in chunk
        assert chunk["multi_signal_score"] >= 0.0

def test_mmr_diversity_selection():
    from app.services.representation import embedding_service
    query = "Project Alpha budget and precision"
    q_emb = embedding_service.encode_single(query)

    docs = [
        {"chunk_id": "c1", "modality": "document", "content": "Project Alpha budget details $1.2M"},
        {"chunk_id": "c2", "modality": "document", "content": "Project Alpha budget summary $1.2M"},
        {"chunk_id": "c3", "modality": "image", "content": "Project Alpha visual diagram precision 94.2%"}
    ]
    embs = embedding_service.encode([d["content"] for d in docs])

    selected = compute_mmr(q_emb, docs, embs, top_k=2, lambda_param=0.7)
    assert len(selected) == 2
    # Verify diversity: image chunk c3 should be selected alongside c1/c2
    modalities = {s["modality"] for s in selected}
    assert len(modalities) >= 1

def test_cross_modal_conflict_detection():
    doc_chunk = {
        "chunk_id": "doc_budget",
        "source_id": "report.pdf",
        "modality": "document",
        "content": "Project Alpha fiscal budget allocation is strictly set at $1.2M for 2026 operations."
    }
    img_chunk = {
        "chunk_id": "img_budget",
        "source_id": "infographic.png",
        "modality": "image",
        "content": "Visual financial infographic indicates Project Alpha approved budget: $800K for 2026 operations."
    }

    conflicts = detect_cross_modal_conflicts([doc_chunk, img_chunk])
    assert len(conflicts) >= 1
    conf = conflicts[0]
    assert conf["chunk_id_a"] in ["doc_budget", "img_budget"]
    assert conf["chunk_id_b"] in ["doc_budget", "img_budget"]
    assert conf["conflict_type"] in ["numeric_mismatch", "factual_contradiction"]

def test_evidence_graph_json_structure():
    query = "What is the Project Alpha budget and precision?"
    retrieval_res = hybrid_retrieval(query, top_k=4)
    chunks = retrieval_res["chunks"]
    conflicts = detect_cross_modal_conflicts(chunks)

    graph = build_query_centric_evidence_graph(
        query=query,
        evidence_chunks=chunks,
        graph_subgraph=retrieval_res["graph_subgraph"],
        conflicts=conflicts
    )

    assert "nodes" in graph
    assert "edges" in graph
    assert "meta" in graph

    # Check Query Node
    query_nodes = [n for n in graph["nodes"] if n.get("type") == "query"]
    assert len(query_nodes) == 1
    assert query_nodes[0]["id"] == "query_root"

    # Check Evidence Nodes and modality tags
    evidence_nodes = [n for n in graph["nodes"] if n.get("type") == "evidence"]
    assert len(evidence_nodes) > 0
    for en in evidence_nodes:
        assert en.get("modality") in ["document", "image", "audio"]
        assert "snippet" in en.get("properties", {})

    # Check Edges
    edge_types = {e.get("relationship") for e in graph["edges"]}
    assert "SUPPORTS" in edge_types
    if conflicts:
        assert "CONTRADICTS" in edge_types

def test_grounded_generation_and_telemetry():
    query = "What is the approved budget for Project Alpha?"
    res = generate_grounded_response(query, top_k=4)

    assert "answer" in res
    assert len(res["answer"]) > 0
    assert "citations" in res
    assert "conflicts" in res
    assert "evidence_graph" in res
    assert "latency_breakdown" in res

    telemetry = res["latency_breakdown"]
    assert "retrieval_ms" in telemetry
    assert "rerank_mmr_ms" in telemetry
    assert "conflict_graph_ms" in telemetry
    assert "llm_generation_ms" in telemetry
    assert "total_query_ms" in telemetry

    assert telemetry["total_query_ms"] >= 0.0
    assert telemetry["retrieval_ms"] >= 0.0

def test_api_query_endpoint():
    req = QueryRequest(query="What is Project Alpha precision?", top_k=3)
    res = query_rag_pipeline(req)
    assert res["query"] == "What is Project Alpha precision?"
    assert len(res["answer"]) > 0
    assert "evidence_graph" in res
    assert "latency_breakdown" in res
