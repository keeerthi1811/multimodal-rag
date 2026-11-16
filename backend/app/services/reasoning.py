import re
import json
import logging
from typing import List, Dict, Any, Optional

from app.config import settings
from app.db.groq_client import groq_wrapper

logger = logging.getLogger(__name__)

def detect_cross_modal_conflicts(evidence_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Stage 5: Cross-modal conflict detection using Groq structured JSON evaluation.
    Preserves both competing claims explicitly with CONTRADICTS flags.
    """
    if len(evidence_chunks) < 2:
        return []

    # Format chunks for LLM evaluation
    chunks_context = []
    for c in evidence_chunks:
        chunks_context.append(
            f"Chunk ID: {c.get('chunk_id')}\n"
            f"Modality: {c.get('modality')}\n"
            f"Source: {c.get('source_id')}\n"
            f"Content: {c.get('content')}\n"
        )
    formatted_input = "\n---\n".join(chunks_context)

    # 1. Groq Structured JSON evaluation if configured
    if groq_wrapper.is_configured:
        try:
            prompt = f"""
            You are a strict cross-modal factual conflict detection engine.
            Analyze the following evidence chunks ingested from different modalities (Document, Image, Audio).
            Detect any contradictory facts, conflicting figures, discrepant dates, or conflicting statements between chunks.
            
            Return ONLY a valid JSON object matching this schema:
            {{
              "has_conflict": true or false,
              "conflicts": [
                {{
                  "chunk_id_a": "ID of first chunk",
                  "chunk_id_b": "ID of second chunk",
                  "source_a": "Source of chunk A",
                  "source_b": "Source of chunk B",
                  "modality_a": "modality of A",
                  "modality_b": "modality of B",
                  "claim_a": "exact factual statement in A",
                  "claim_b": "conflicting statement in B",
                  "conflict_type": "numeric_mismatch | temporal_mismatch | factual_contradiction",
                  "explanation": "Clear explanation of contradiction"
                }}
              ]
            }}

            Evidence Chunks:
            {formatted_input}
            """
            response_str = groq_wrapper.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=settings.groq_model,
                response_format={"type": "json_object"},
                temperature=0.0
            )
            parsed = json.loads(response_str)
            if parsed.get("has_conflict") and parsed.get("conflicts"):
                return parsed["conflicts"]
        except Exception as e:
            logger.warning(f"Groq conflict detection failed: {e}. Running fallback rule-based conflict detector.")

    # 2. Deterministic Fallback Conflict Detection
    # Detects true factual contradictions (budget discrepancies, conflicting benchmark accuracies) across modalities
    conflicts = []
    for i in range(len(evidence_chunks)):
        for j in range(i + 1, len(evidence_chunks)):
            c1 = evidence_chunks[i]
            c2 = evidence_chunks[j]

            t1 = c1["content"].lower()
            t2 = c2["content"].lower()

            # Check 1: Budget / Funding Conflict ($1.2M vs $800K)
            has_budget_1 = ("budget" in t1 or "fiscal" in t1 or "allocation" in t1)
            has_budget_2 = ("budget" in t2 or "fiscal" in t2 or "allocation" in t2)
            if has_budget_1 and has_budget_2:
                # Find currency amounts
                amounts1 = re.findall(r'\$[\d,]+(?:\.\d+)?(?:\s*[MK]|\b)', c1["content"])
                amounts2 = re.findall(r'\$[\d,]+(?:\.\d+)?(?:\s*[MK]|\b)', c2["content"])
                if amounts1 and amounts2:
                    # Normalize amounts (e.g. $1.2M vs $800K)
                    def norm_amt(s: str) -> float:
                        s_clean = s.replace("$", "").replace(",", "").strip()
                        if "m" in s_clean.lower():
                            return float(s_clean.lower().replace("m", "")) * 1_000_000
                        if "k" in s_clean.lower():
                            return float(s_clean.lower().replace("k", "")) * 1_000
                        return float(s_clean)
                    val1 = norm_amt(amounts1[0])
                    val2 = norm_amt(amounts2[0])
                    if abs(val1 - val2) > 10_000:
                        conflicts.append({
                            "chunk_id_a": c1["chunk_id"],
                            "chunk_id_b": c2["chunk_id"],
                            "source_a": c1["source_id"],
                            "source_b": c2["source_id"],
                            "modality_a": c1["modality"],
                            "modality_b": c2["modality"],
                            "claim_a": f"Approved budget stated as {amounts1[0]}",
                            "claim_b": f"Approved budget stated as {amounts2[0]}",
                            "conflict_type": "numeric_mismatch",
                            "explanation": f"Factual budget contradiction: {c1['source_id']} ({c1['modality']}) specifies {amounts1[0]} whereas {c2['source_id']} ({c2['modality']}) states {amounts2[0]}."
                        })
                        continue

            # Check 2: Metric / Precision Percentage Conflict (e.g. 94.2% vs 78.5%)
            has_metric_1 = ("precision" in t1 or "accuracy" in t1)
            has_metric_2 = ("precision" in t2 or "accuracy" in t2)
            if has_metric_1 and has_metric_2:
                pcts1 = re.findall(r'(\d+(?:\.\d+)?%)', c1["content"])
                pcts2 = re.findall(r'(\d+(?:\.\d+)?%)', c2["content"])
                if pcts1 and pcts2 and pcts1[0] != pcts2[0]:
                    conflicts.append({
                        "chunk_id_a": c1["chunk_id"],
                        "chunk_id_b": c2["chunk_id"],
                        "source_a": c1["source_id"],
                        "source_b": c2["source_id"],
                        "modality_a": c1["modality"],
                        "modality_b": c2["modality"],
                        "claim_a": f"Reports precision of {pcts1[0]}",
                        "claim_b": f"Reports precision of {pcts2[0]}",
                        "conflict_type": "numeric_mismatch",
                        "explanation": f"Performance discrepancy: {c1['source_id']} states {pcts1[0]} while {c2['source_id']} states {pcts2[0]}."
                    })
                    continue

    return conflicts

def build_query_centric_evidence_graph(
    query: str,
    evidence_chunks: List[Dict[str, Any]],
    graph_subgraph: Dict[str, Any],
    conflicts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 6: Constructs temporary in-memory subgraph JSON:
    - Nodes: Query, Entities, Evidence Chunks (with modality badges)
    - Edges: SUPPORTS, MENTIONS, CONTRADICTS
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids: Set[str] = set()

    # 1. Query Root Node
    query_id = "query_root"
    nodes.append({
        "id": query_id,
        "label": "Query",
        "name": query,
        "type": "query",
        "properties": {"text": query}
    })
    node_ids.add(query_id)

    # 2. Evidence Chunk Nodes
    for chunk in evidence_chunks:
        cid = chunk["chunk_id"]
        if cid not in node_ids:
            nodes.append({
                "id": cid,
                "label": "Evidence",
                "name": f"{chunk['modality'].upper()}: {chunk['source_id']}",
                "type": "evidence",
                "modality": chunk.get("modality", "document"),
                "source_id": chunk.get("source_id", ""),
                "score": chunk.get("multi_signal_score", 0.0),
                "properties": {
                    "content": chunk.get("content", ""),
                    "snippet": chunk.get("content", "")[:120] + "...",
                    "modality": chunk.get("modality", "document"),
                    "page_num": chunk.get("metadata", {}).get("page_num"),
                    "start_time": chunk.get("metadata", {}).get("start_time"),
                    "end_time": chunk.get("metadata", {}).get("end_time"),
                }
            })
            node_ids.add(cid)

        # Edge from Evidence to Query: SUPPORTS
        edges.append({
            "id": f"edge_{cid}_to_query",
            "source": cid,
            "target": query_id,
            "relationship": "SUPPORTS",
            "properties": {"score": chunk.get("multi_signal_score", 0.5)}
        })

    # 3. Entity Nodes from Graph Subgraph
    for gnode in graph_subgraph.get("nodes", []):
        gid = gnode.get("id", "")
        gname = gnode.get("properties", {}).get("name", gid)
        if gid not in node_ids:
            nodes.append({
                "id": gid,
                "label": "Entity",
                "name": gname,
                "type": "entity",
                "properties": gnode.get("properties", {})
            })
            node_ids.add(gid)

    # 4. Graph Subgraph Relational Edges
    for gedge in graph_subgraph.get("edges", []):
        src = gedge.get("source")
        tgt = gedge.get("target")
        if src in node_ids and tgt in node_ids:
            edges.append({
                "id": f"edge_{src}_{tgt}_{gedge.get('relationship', 'REL')}",
                "source": src,
                "target": tgt,
                "relationship": gedge.get("relationship", "RELATED_TO"),
                "properties": gedge.get("properties", {})
            })

    # Connect Evidence chunks to mentioned Entities
    for chunk in evidence_chunks:
        cid = chunk["chunk_id"]
        c_text = chunk.get("content", "").lower()
        for node in nodes:
            if node["type"] == "entity":
                ename = node["name"].lower()
                if len(ename) > 2 and ename in c_text:
                    edges.append({
                        "id": f"mentions_{cid}_{node['id']}",
                        "source": cid,
                        "target": node["id"],
                        "relationship": "MENTIONS",
                        "properties": {}
                    })

    # 5. Add CONTRADICTS Edges
    for idx, conf in enumerate(conflicts):
        src = conf.get("chunk_id_a")
        tgt = conf.get("chunk_id_b")
        if src in node_ids and tgt in node_ids:
            edges.append({
                "id": f"conflict_{src}_{tgt}_{idx}",
                "source": src,
                "target": tgt,
                "relationship": "CONTRADICTS",
                "properties": {
                    "conflict_type": conf.get("conflict_type", "factual_contradiction"),
                    "claim_a": conf.get("claim_a", ""),
                    "claim_b": conf.get("claim_b", ""),
                    "explanation": conf.get("explanation", "")
                }
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "query": query,
            "evidence_count": len(evidence_chunks),
            "entity_count": sum(1 for n in nodes if n["type"] == "entity"),
            "conflicts_count": len(conflicts)
        }
    }

def contextual_evidence_fusion(
    query: str,
    evidence_chunks: List[Dict[str, Any]],
    graph_subgraph: Dict[str, Any],
    conflicts: List[Dict[str, Any]]
) -> str:
    """
    Stage 7: Contextual Evidence Fusion.
    Synthesizes refined multimodal evidence, graph relationships, and explicit conflict warnings.
    """
    sections = []
    sections.append(f"# USER QUERY:\n{query}\n")

    # 1. Explicit Conflict Warnings
    if conflicts:
        sections.append("## [CRITICAL NOTICE: CROSS-MODAL CONFLICTS DETECTED]")
        sections.append("The retrieved multimodal sources contain contradictory claims. Both perspectives must be explicitly acknowledged:")
        for idx, conf in enumerate(conflicts, 1):
            sections.append(
                f"{idx}. Conflict between {conf['modality_a'].upper()} ({conf['source_a']}) and {conf['modality_b'].upper()} ({conf['source_b']}):\n"
                f"   - {conf['source_a']} asserts: \"{conf['claim_a']}\"\n"
                f"   - {conf['source_b']} asserts: \"{conf['claim_b']}\"\n"
                f"   - Analysis: {conf['explanation']}"
            )
        sections.append("")

    # 2. Multimodal Evidence Chunks
    sections.append("## VERIFIED MULTIMODAL EVIDENCE CHUNKS:")
    for idx, c in enumerate(evidence_chunks, 1):
        mod = c.get("modality", "document").upper()
        sid = c.get("source_id", "source")
        cid = c.get("chunk_id", f"c{idx}")
        meta = c.get("metadata", {})
        
        cite_tag = f"[{mod}: {sid}"
        if "page_num" in meta:
            cite_tag += f", p.{meta['page_num']}"
        if "start_time" in meta and "end_time" in meta:
            cite_tag += f", {meta['start_time']:.1f}s-{meta['end_time']:.1f}s"
        cite_tag += "]"

        sections.append(
            f"Evidence #{idx} {cite_tag} (ID: {cid}):\n"
            f"{c.get('content')}\n"
        )

    # 3. Knowledge Graph Context
    kg_triples = []
    for edge in graph_subgraph.get("edges", []):
        src_id = edge.get("source")
        tgt_id = edge.get("target")
        rel = edge.get("relationship", "REL")
        kg_triples.append(f"({src_id}) -[{rel}]-> ({tgt_id})")

    if kg_triples:
        sections.append("## GRAPH RELATIONSHIPS:")
        sections.append("\n".join(kg_triples[:10]))
        sections.append("")

    return "\n".join(sections)
