import sys
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

# Ensure backend in path
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.db.weaviate_client import weaviate_wrapper
from app.db.neo4j_client import neo4j_wrapper
from app.services.ingestion import ingest_file
from app.services.representation import represent_and_store_chunks, embedding_service
from app.services.retrieval import hybrid_retrieval, extract_query_entities
from app.services.reasoning import detect_cross_modal_conflicts
from app.services.generator import generate_grounded_response

logger = logging.getLogger(__name__)

EVAL_DIR = ROOT_DIR / "evaluation"
SAMPLE_DATA_DIR = EVAL_DIR / "sample_data"
RESULTS_FILE = EVAL_DIR / "results" / "latest_metrics.json"

def run_evaluation_benchmark(rate_limit_pause_sec: float = 0.5) -> Dict[str, Any]:
    """
    Executes automated multimodal benchmark:
    1. Ingests multimodal dataset (PDF, PNG, WAV) and records ingestion latency.
    2. Compares Vector-Only, Graph-Only, and Proposed Hybrid+Rerank/MMR.
    3. Computes Retrieval (Precision@K, Recall@K, MRR), Conflict Detection (Precision, Recall),
       and Stage Latency breakdown.
    4. Persists results to evaluation/results/latest_metrics.json.
    """
    print("=== Starting Unified Multimodal RAG Benchmark ===")
    # Delete only previous benchmark sample sources so user uploaded documents are never wiped
    benchmark_sources = [
        "alpha_annual_report.pdf", "alpha_annual_report",
        "alpha_financial_infographic.png", "alpha_financial_infographic",
        "alpha_standup_recording.wav", "alpha_standup_recording",
        "report_alpha.pdf", "report_alpha",
        "budget_infographic.png", "budget_infographic",
        "standup_audio.wav", "standup_audio"
    ]
    for sid in benchmark_sources:
        weaviate_wrapper.delete_source(sid)
        neo4j_wrapper.delete_source(sid)

    # Step 1: Multimodal Ingestion & Latency Profiling
    ingestion_latency = {}
    files_to_ingest = [
        ("document", SAMPLE_DATA_DIR / "alpha_annual_report.pdf"),
        ("image", SAMPLE_DATA_DIR / "alpha_financial_infographic.png"),
        ("audio", SAMPLE_DATA_DIR / "alpha_standup_recording.wav"),
    ]

    total_chunks_indexed = 0
    total_triples_indexed = 0

    for modality, fpath in files_to_ingest:
        if not fpath.exists():
            from evaluation.generate_sample_data import generate_all
            generate_all()

        t0 = time.perf_counter()
        chunks = ingest_file(str(fpath), source_id=fpath.stem)
        t_ingest_done = time.perf_counter()
        store_res = represent_and_store_chunks(chunks)
        t_store_done = time.perf_counter()

        ingest_time_ms = round((t_ingest_done - t0) * 1000, 2)
        rep_time_ms = round((t_store_done - t_ingest_done) * 1000, 2)
        total_mod_ms = round((t_store_done - t0) * 1000, 2)

        ingestion_latency[modality] = {
            "file": fpath.name,
            "chunks_count": len(chunks),
            "ingest_ms": ingest_time_ms,
            "representation_ms": rep_time_ms,
            "total_ms": total_mod_ms
        }
        total_chunks_indexed += len(chunks)
        total_triples_indexed += store_res.get("triples_stored", 0)

    # Step 2: Load Ground Truth
    gt_file = SAMPLE_DATA_DIR / "ground_truth.json"
    with open(gt_file, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    test_cases = ground_truth.get("test_cases", [])
    K = 3

    # Evaluation accumulators for 3 modes
    modes = ["vector_only", "graph_only", "proposed_hybrid"]
    metrics_by_mode = {
        m: {
            "precision_k": [],
            "recall_k": [],
            "mrr": [],
            "latency_ms": []
        }
        for m in modes
    }

    # Conflict detection evaluation accumulators
    conflict_eval = {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 0,
        "detected_conflicts": []
    }

    # Stage-wise latency accumulators for proposed framework
    stage_latencies = {
        "retrieval_ms": [],
        "rerank_mmr_ms": [],
        "conflict_graph_ms": [],
        "llm_generation_ms": [],
        "total_query_ms": []
    }

    for tc in test_cases:
        query = tc["query"]
        target_sources = set(tc["relevant_sources"])
        target_keywords = [kw.lower() for kw in tc["target_keywords"]]
        has_true_conflict = tc.get("has_conflict", False)

        # Mode 1: Vector-Only Retrieval
        t0 = time.perf_counter()
        q_emb = embedding_service.encode_single(query)
        v_results = weaviate_wrapper.search(q_emb, top_k=K)
        t_v = time.perf_counter()
        v_latency = round((t_v - t0) * 1000, 2)
        _compute_retrieval_stats(v_results, target_sources, target_keywords, K, metrics_by_mode["vector_only"], v_latency)

        # Mode 2: Graph-Only Retrieval
        t0 = time.perf_counter()
        q_ents = extract_query_entities(query)
        g_sub = neo4j_wrapper.query_neighborhood(q_ents, hops=2)
        g_results = []
        for edge in g_sub.get("edges", []):
            cid = edge.get("properties", {}).get("chunk_id")
            if cid and cid in weaviate_wrapper.local_store.documents:
                doc = weaviate_wrapper.local_store.documents[cid]
                if doc not in g_results:
                    g_results.append(doc)
            if len(g_results) >= K:
                break
        t_g = time.perf_counter()
        g_latency = round((t_g - t0) * 1000, 2)
        _compute_retrieval_stats(g_results, target_sources, target_keywords, K, metrics_by_mode["graph_only"], g_latency)

        # Mode 3: Proposed Hybrid + Rerank/MMR + Conflict Detection + Grounded Generation
        time.sleep(rate_limit_pause_sec)  # Groq rate pacing
        full_result = generate_grounded_response(
            query=query,
            top_k=K,
            similarity_weight=0.5,
            graph_weight=0.5,
            enable_mmr=True,
            mmr_lambda=0.7
        )
        h_chunks = full_result.get("evidence_chunks", [])
        lat = full_result.get("latency_breakdown", {})

        _compute_retrieval_stats(h_chunks, target_sources, target_keywords, K, metrics_by_mode["proposed_hybrid"], lat.get("total_query_ms", 50.0))

        # Conflict Detection Evaluation
        detected_conflicts = full_result.get("conflicts", [])
        has_detected_conflict = len(detected_conflicts) > 0

        if has_true_conflict and has_detected_conflict:
            conflict_eval["tp"] += 1
            conflict_eval["detected_conflicts"].extend(detected_conflicts)
        elif not has_true_conflict and has_detected_conflict:
            conflict_eval["fp"] += 1
        elif has_true_conflict and not has_detected_conflict:
            conflict_eval["fn"] += 1
        else:
            conflict_eval["tn"] += 1

        # Accumulate Stage Latencies
        for k in stage_latencies:
            if k in lat:
                stage_latencies[k].append(lat[k])

    # Compute final aggregate scores
    retrieval_comparison = {}
    for m in modes:
        p_list = metrics_by_mode[m]["precision_k"]
        r_list = metrics_by_mode[m]["recall_k"]
        mrr_list = metrics_by_mode[m]["mrr"]
        lat_list = metrics_by_mode[m]["latency_ms"]

        retrieval_comparison[m] = {
            "precision_at_k": round(float(sum(p_list) / len(p_list)) if p_list else 0.0, 4),
            "recall_at_k": round(float(sum(r_list) / len(r_list)) if r_list else 0.0, 4),
            "mrr": round(float(sum(mrr_list) / len(mrr_list)) if mrr_list else 0.0, 4),
            "mean_latency_ms": round(float(sum(lat_list) / len(lat_list)) if lat_list else 0.0, 2)
        }

    # Compute Conflict Detection Precision & Recall
    tp = conflict_eval["tp"]
    fp = conflict_eval["fp"]
    fn = conflict_eval["fn"]
    conflict_precision = round(tp / (tp + fp) if (tp + fp) > 0 else 1.0, 4)
    conflict_recall = round(tp / (tp + fn) if (tp + fn) > 0 else 1.0, 4)
    conflict_f1 = round(2 * conflict_precision * conflict_recall / (conflict_precision + conflict_recall) if (conflict_precision + conflict_recall) > 0 else 0.0, 4)

    # Compute Stage Latency Averages
    mean_stage_latencies = {
        k: round(float(sum(v) / len(v)) if v else 0.0, 2)
        for k, v in stage_latencies.items()
    }

    results_payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_summary": {
            "total_test_queries": len(test_cases),
            "total_indexed_chunks": total_chunks_indexed,
            "total_indexed_triples": total_triples_indexed
        },
        "ingestion_latency_by_modality": ingestion_latency,
        "retrieval_benchmark_comparison": {
            "k": K,
            "vector_only": retrieval_comparison["vector_only"],
            "graph_only": retrieval_comparison["graph_only"],
            "proposed_hybrid": retrieval_comparison["proposed_hybrid"]
        },
        "conflict_detection_metrics": {
            "conflict_precision": conflict_precision,
            "conflict_recall": conflict_recall,
            "conflict_f1": conflict_f1,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": conflict_eval["tn"],
            "sample_conflict": conflict_eval["detected_conflicts"][:1]
        },
        "stage_latency_profiling_ms": mean_stage_latencies
    }

    # Persist results to JSON
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    print(f"Benchmark finished. Results saved to {RESULTS_FILE}")
    return results_payload

def _compute_retrieval_stats(results: List[Dict[str, Any]], target_sources: set, target_keywords: List[str], k: int, accum: Dict[str, list], latency_ms: float):
    accum["latency_ms"].append(latency_ms)
    if not results:
        accum["precision_k"].append(0.0)
        accum["recall_k"].append(0.0)
        accum["mrr"].append(0.0)
        return

    relevant_retrieved = 0
    first_rel_rank = 0

    for idx, item in enumerate(results[:k], 1):
        content = item.get("content", "").lower()
        src = item.get("source_id", "")
        is_relevant = src in target_sources or any(kw in content for kw in target_keywords)
        if is_relevant:
            relevant_retrieved += 1
            if first_rel_rank == 0:
                first_rel_rank = idx

    p_k = relevant_retrieved / k
    r_k = relevant_retrieved / max(1, len(target_sources))
    mrr = 1.0 / first_rel_rank if first_rel_rank > 0 else 0.0

    accum["precision_k"].append(p_k)
    accum["recall_k"].append(min(1.0, r_k))
    accum["mrr"].append(mrr)

if __name__ == "__main__":
    res = run_evaluation_benchmark(rate_limit_pause_sec=0.1)
    print(json.dumps(res, indent=2))
