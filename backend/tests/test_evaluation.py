import json
from pathlib import Path
import pytest
from app.main import get_latest_metrics, run_evaluation

def test_latest_metrics_structure():
    metrics = get_latest_metrics()
    assert "timestamp" in metrics
    assert "dataset_summary" in metrics
    assert "ingestion_latency_by_modality" in metrics
    assert "retrieval_benchmark_comparison" in metrics
    assert "conflict_detection_metrics" in metrics
    assert "stage_latency_profiling_ms" in metrics

    # Ingestion latency validation
    ingestion = metrics["ingestion_latency_by_modality"]
    assert "document" in ingestion
    assert "image" in ingestion
    assert "audio" in ingestion

    # Retrieval benchmark comparison validation
    retrieval = metrics["retrieval_benchmark_comparison"]
    assert "vector_only" in retrieval
    assert "graph_only" in retrieval
    assert "proposed_hybrid" in retrieval
    for mode in ["vector_only", "graph_only", "proposed_hybrid"]:
        assert "precision_at_k" in retrieval[mode]
        assert "recall_at_k" in retrieval[mode]
        assert "mrr" in retrieval[mode]
        assert "mean_latency_ms" in retrieval[mode]
        assert retrieval[mode]["recall_at_k"] >= 0.0

    # Conflict detection metrics validation
    conflicts = metrics["conflict_detection_metrics"]
    assert "conflict_precision" in conflicts
    assert "conflict_recall" in conflicts
    assert "conflict_f1" in conflicts
    assert "true_positives" in conflicts

    # Stage latency validation
    latencies = metrics["stage_latency_profiling_ms"]
    assert "retrieval_ms" in latencies
    assert "rerank_mmr_ms" in latencies
    assert "conflict_graph_ms" in latencies
    assert "llm_generation_ms" in latencies
    assert "total_query_ms" in latencies
    assert latencies["total_query_ms"] > 0.0
