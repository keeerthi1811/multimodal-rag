import re
import logging
from typing import List, Dict, Any, Optional, Set
import numpy as np

from app.config import settings
from app.db.weaviate_client import weaviate_wrapper
from app.db.neo4j_client import neo4j_wrapper
from app.services.representation import embedding_service

logger = logging.getLogger(__name__)

class RerankerService:
    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                try:
                    self._model = CrossEncoder(settings.reranker_model, max_length=512, local_files_only=True)
                    logger.info(f"Loaded cached CrossEncoder reranker: {settings.reranker_model}")
                except Exception:
                    # If not cached locally and in offline sandbox mode, use lexical-semantic cross-scoring
                    self._model = "fallback"
            except Exception as e:
                logger.info(f"CrossEncoder offline/fallback mode ({e}). Using lexical-semantic cross-scoring.")
                self._model = "fallback"
        return self._model

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        model = self._get_model()
        if model != "fallback" and model is not None:
            try:
                pairs = [[query, c["content"]] for c in candidates]
                scores = model.predict(pairs)
                for idx, c in enumerate(candidates):
                    c["rerank_score"] = float(scores[idx])
                candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
                return candidates[:top_k]
            except Exception as e:
                logger.warning(f"Reranker predict failed: {e}. Using fallback cross-score.")

        # Fallback cross-scoring: query term density, exact phrase matching, and positional weighting
        q_tokens = set(re.findall(r'\w+', query.lower()))
        for c in candidates:
            content_lower = c["content"].lower()
            c_tokens = re.findall(r'\w+', content_lower)
            if not c_tokens or not q_tokens:
                c["rerank_score"] = c.get("multi_signal_score", 0.5)
                continue

            matches = sum(1 for tok in c_tokens if tok in q_tokens)
            density = matches / len(c_tokens)
            coverage = len(set(c_tokens) & q_tokens) / len(q_tokens)
            phrase_bonus = 0.25 if query.lower() in content_lower else 0.0
            
            combined_score = 0.4 * coverage + 0.3 * density + 0.3 * c.get("multi_signal_score", 0.5) + phrase_bonus
            c["rerank_score"] = round(combined_score, 4)

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates[:top_k]

reranker_service = RerankerService()

def compute_mmr(
    query_emb: List[float],
    candidate_chunks: List[Dict[str, Any]],
    candidate_embs: List[List[float]],
    top_k: int = 5,
    lambda_param: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Maximal Marginal Relevance (MMR) selection:
    Balances relevance to query against redundancy with already selected chunks,
    fostering cross-modal diversity.
    """
    if not candidate_chunks:
        return []
    if len(candidate_chunks) <= top_k:
        return candidate_chunks

    q_vec = np.array(query_emb, dtype=np.float32)
    q_norm = np.linalg.norm(q_vec) or 1.0
    doc_vecs = [np.array(e, dtype=np.float32) / (np.linalg.norm(e) or 1.0) for e in candidate_embs]

    selected_indices: List[int] = []
    unselected_indices = list(range(len(candidate_chunks)))

    # Initial best match
    sim_to_query = [float(np.dot(q_vec / q_norm, dv)) for dv in doc_vecs]
    first_idx = int(np.argmax(sim_to_query))
    selected_indices.append(first_idx)
    unselected_indices.remove(first_idx)

    # Iterative MMR selection
    while len(selected_indices) < top_k and unselected_indices:
        best_mmr_score = -float("inf")
        best_candidate = unselected_indices[0]

        for cand_idx in unselected_indices:
            relevance = sim_to_query[cand_idx]
            
            # Redundancy: max similarity to any already selected document
            redundancy = max([float(np.dot(doc_vecs[cand_idx], doc_vecs[sel_idx])) for sel_idx in selected_indices])
            
            # Modality bonus to promote cross-modal representation
            cand_mod = candidate_chunks[cand_idx].get("modality", "")
            sel_mods = {candidate_chunks[s].get("modality", "") for s in selected_indices}
            mod_bonus = 0.08 if cand_mod not in sel_mods else 0.0

            mmr_score = lambda_param * relevance - (1.0 - lambda_param) * redundancy + mod_bonus
            if mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_candidate = cand_idx

        selected_indices.append(best_candidate)
        unselected_indices.remove(best_candidate)

    return [candidate_chunks[i] for i in selected_indices]

def extract_query_entities(query: str) -> List[str]:
    """Extracts named entities or key search tokens from query string."""
    tokens = re.findall(r'\b[A-Z][a-zA-Z0-9_-]+\b', query)
    words = re.findall(r'\b[a-zA-Z0-9_-]{3,}\b', query)
    candidates = list(dict.fromkeys(tokens + [w.capitalize() for w in words]))
    return candidates[:8]

def hybrid_retrieval(
    query: str,
    top_k: int = 5,
    similarity_weight: float = 0.5,
    graph_weight: float = 0.5,
    enable_mmr: bool = True,
    mmr_lambda: float = 0.7,
    source_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes 7-Stage Retrieval stages 1 through 4:
    1. Hybrid Retrieval (Vector + KG neighborhood)
    2. Multi-Signal Scoring (semantic + graph proximity + modality corroboration + reliability)
    3. Reranking (BAAI/bge-reranker-base CrossEncoder)
    4. MMR Diversity Selection
    """
    # 1. Vector Search
    query_emb = embedding_service.encode_single(query)
    vector_results = weaviate_wrapper.search(query_emb, top_k=top_k * 2)

    # 2. Graph Retrieval via 1-2 hop neighborhood
    query_entities = extract_query_entities(query)
    graph_subgraph = neo4j_wrapper.query_neighborhood(query_entities, hops=2)
    graph_nodes = graph_subgraph.get("nodes", [])
    graph_edges = graph_subgraph.get("edges", [])

    # Map graph edges to chunk_ids associated with graph paths
    graph_chunk_ids: Set[str] = set()
    graph_hop_distance: Dict[str, float] = {}

    for edge in graph_edges:
        props = edge.get("properties", {})
        cid = props.get("chunk_id")
        if cid:
            graph_chunk_ids.add(cid)
            # 1-hop association gives higher proximity score
            graph_hop_distance[cid] = 1.0

    # Combine candidates from Vector and Graph
    candidates_dict: Dict[str, Dict[str, Any]] = {}

    for vr in vector_results:
        cid = vr["chunk_id"]
        candidates_dict[cid] = {
            "chunk_id": cid,
            "source_id": vr.get("source_id", ""),
            "modality": vr.get("modality", "document"),
            "content": vr.get("content", ""),
            "metadata": vr.get("metadata", {}),
            "vector_score": float(vr.get("score", 0.0)),
            "graph_score": 0.0,
            "in_vector": True,
            "in_graph": False
        }

    for cid in graph_chunk_ids:
        if cid in candidates_dict:
            candidates_dict[cid]["in_graph"] = True
            candidates_dict[cid]["graph_score"] = graph_hop_distance.get(cid, 0.7)
        else:
            # Graph-only hit: retrieve document from local vector store
            doc = weaviate_wrapper.local_store.documents.get(cid)
            if doc:
                candidates_dict[cid] = {
                    "chunk_id": cid,
                    "source_id": doc.get("source_id", ""),
                    "modality": doc.get("modality", "document"),
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {}),
                    "vector_score": 0.3,
                    "graph_score": graph_hop_distance.get(cid, 0.7),
                    "in_vector": False,
                    "in_graph": True
                }

    candidate_list = list(candidates_dict.values())

    # Optional source filtering when user selects a specific scope
    if source_filter and source_filter.strip().lower() not in ("all", "*"):
        filtered = [
            c for c in candidate_list 
            if c.get("source_id") == source_filter 
            or c.get("metadata", {}).get("source_id") == source_filter 
            or c.get("metadata", {}).get("file_name") == source_filter
        ]
        if filtered:
            candidate_list = filtered

    if not candidate_list:
        return {
            "chunks": [],
            "graph_subgraph": graph_subgraph,
            "query_entities": query_entities
        }

    # 3. Multi-Signal Scoring
    # Check modality counts for corroboration bonus
    modality_counts: Dict[str, int] = {}
    for c in candidate_list:
        mod = c["modality"]
        modality_counts[mod] = modality_counts.get(mod, 0) + 1

    for c in candidate_list:
        v_score = c["vector_score"]
        g_score = c["graph_score"]
        
        # Corroboration bonus: chunk corroborated if other modalities present
        corroboration = 0.15 if len(modality_counts) > 1 and modality_counts.get(c["modality"], 0) >= 1 else 0.0
        reliability = 1.0  # standard source reliability

        final_score = (
            similarity_weight * v_score +
            graph_weight * g_score +
            corroboration
        ) * reliability
        c["multi_signal_score"] = round(min(1.0, final_score), 4)

    # 4. Reranking using CrossEncoder
    reranked = reranker_service.rerank(query, candidate_list, top_k=top_k * 2)

    # 5. MMR Diversity Selection
    if enable_mmr and len(reranked) > top_k:
        reranked_texts = [r["content"] for r in reranked]
        reranked_embs = embedding_service.encode(reranked_texts)
        final_selected = compute_mmr(
            query_emb=query_emb,
            candidate_chunks=reranked,
            candidate_embs=reranked_embs,
            top_k=top_k,
            lambda_param=mmr_lambda
        )
    else:
        final_selected = reranked[:top_k]

    return {
        "chunks": final_selected,
        "graph_subgraph": graph_subgraph,
        "query_entities": query_entities,
        "total_candidates_found": len(candidate_list)
    }
