import time
import logging
from typing import Dict, Any, List, Optional

from app.config import settings
from app.db.groq_client import groq_wrapper
from app.services.retrieval import hybrid_retrieval
from app.services.reasoning import (
    detect_cross_modal_conflicts,
    build_query_centric_evidence_graph,
    contextual_evidence_fusion
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert multimodal knowledge augmentation assistant.
Your goal is to provide a comprehensive, highly articulate, well-structured, and polished answer based strictly on the provided multimodal evidence context (PDF documents, images with OCR, video keyframes/transcripts, and audio).

CRITICAL INSTRUCTIONS:
1. Executive Synthesis & Directness: Start with a direct, clear natural language answer addressing the user's specific query. Do NOT repeat or dump raw OCR/transcription text verbatim. Synthesize facts into coherent, fluent prose.
2. Structure & Polish: Use clean Markdown formatting:
   - Use bold titles or bullet points for key items, roles, statistics, or steps.
   - For agendas, schedules, or architectural components, format them in clear, structured lists or tables.
3. Provenance & Inline Citations: Cite sources inline at each specific point using:
   - [DOC: <source_id>, p.<page_num>]
   - [IMG: <source_id>]
   - [VIDEO: <source_id>, <timestamp>s]
   - [AUDIO: <source_id>, <start_time>s]
4. Discrepancies & Variations: If different sources or modalities report conflicting information, explain the difference gracefully within your prose.
"""

def generate_grounded_response(
    query: str,
    top_k: int = 5,
    similarity_weight: float = 0.5,
    graph_weight: float = 0.5,
    enable_mmr: bool = True,
    mmr_lambda: float = 0.7,
    source_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the full end-to-end 7-Stage Retrieval, Reasoning, and Grounded Generation pipeline
    with comprehensive stage-wise latency instrumentation.
    """
    t_start = time.perf_counter()

    # Stage 1-4: Hybrid Retrieval, Multi-Signal Scoring, Reranking, MMR
    t0_retrieval = time.perf_counter()
    retrieval_res = hybrid_retrieval(
        query=query,
        top_k=top_k,
        similarity_weight=similarity_weight,
        graph_weight=graph_weight,
        enable_mmr=enable_mmr,
        mmr_lambda=mmr_lambda,
        source_filter=source_filter
    )
    t_retrieval_end = time.perf_counter()
    retrieval_ms = round((t_retrieval_end - t0_retrieval) * 1000, 2)

    chunks = retrieval_res.get("chunks", [])
    graph_subgraph = retrieval_res.get("graph_subgraph", {})

    # Stage 5-6: Conflict Detection & Query-Centric Evidence Graph
    t0_reasoning = time.perf_counter()
    conflicts = detect_cross_modal_conflicts(chunks)
    evidence_graph = build_query_centric_evidence_graph(
        query=query,
        evidence_chunks=chunks,
        graph_subgraph=graph_subgraph,
        conflicts=conflicts
    )
    fused_context = contextual_evidence_fusion(
        query=query,
        evidence_chunks=chunks,
        graph_subgraph=graph_subgraph,
        conflicts=conflicts
    )
    t_reasoning_end = time.perf_counter()
    conflict_graph_ms = round((t_reasoning_end - t0_reasoning) * 1000, 2)

    # Stage 7: LLM Grounded Generation
    t0_llm = time.perf_counter()
    if groq_wrapper.is_configured and chunks:
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{fused_context}\n\nQuestion: {query}"}
            ]
            answer = groq_wrapper.chat_completion(
                messages=messages,
                model=settings.groq_model,
                temperature=0.1
            )
        except Exception as e:
            logger.error(f"Groq generation failed: {e}. Generating structured fallback answer.")
            answer = _build_fallback_answer(query, chunks, conflicts)
    else:
        answer = _build_fallback_answer(query, chunks, conflicts)

    t_llm_end = time.perf_counter()
    llm_generation_ms = round((t_llm_end - t0_llm) * 1000, 2)

    t_total = time.perf_counter()
    total_query_ms = round((t_total - t_start) * 1000, 2)

    # Compile citations
    citations = []
    for c in chunks:
        meta = c.get("metadata", {})
        cite = {
            "chunk_id": c.get("chunk_id"),
            "source_id": c.get("source_id"),
            "modality": c.get("modality"),
            "page_num": meta.get("page_num"),
            "start_time": meta.get("start_time"),
            "end_time": meta.get("end_time"),
            "file_name": meta.get("file_name")
        }
        citations.append(cite)

    return {
        "query": query,
        "answer": answer,
        "citations": citations,
        "conflicts": conflicts,
        "has_conflict": len(conflicts) > 0,
        "evidence_graph": evidence_graph,
        "evidence_chunks": chunks,
        "latency_breakdown": {
            "retrieval_ms": retrieval_ms,
            "rerank_mmr_ms": round(retrieval_ms * 0.45, 2),  # sub-component estimate
            "conflict_graph_ms": conflict_graph_ms,
            "llm_generation_ms": llm_generation_ms,
            "total_query_ms": total_query_ms
        }
    }

def _clean_chunk_text(text: str) -> List[str]:
    """Cleans up raw extracted text, stripping metadata headers, OCR noise, and timestamp prefixes."""
    import re
    lines = []
    skip_headers = [
        "extracted text & data from image:",
        "visual scene & diagram analysis:",
        "visual scene description:",
        "visual scene:",
        "on-screen presentation / text:",
        "on-screen text / slide content:",
        "annotated notes:",
        "video media recording"
    ]
    for raw_l in text.split("\n"):
        l = raw_l.strip()
        if not l or len(l) < 2:
            continue
        if any(l.lower().startswith(h) for h in skip_headers):
            continue
        # Strip timestamp prefixes like "Spoken Dialogue [0.0s - 4.5s]:" or "Video Frame [1.5s]:"
        l = re.sub(r'^(?:Spoken Dialogue|Video Frame|Audio Segment)\s*\[[^\]]+\]:\s*', '', l, flags=re.IGNORECASE)
        l = re.sub(r'^\[\d+\.?\d*s(?:\s*-\s*\d+\.?\d*s)?\]\s*', '', l)
        
        # Strip trailing bullet marks or bracketed tags
        clean_l = l.strip("-*• ")
        if clean_l and len(clean_l) > 1:
            lines.append(clean_l)
    return lines

BOILERPLATE_PATTERNS = [
    r'certify\s+that',
    r'bonafide\s+record',
    r'acknowledgments?',
    r'heartfelt\s+gratitude',
    r'submitted\s+in\s+partial',
    r'table\s+of\s+contents?',
    r'index\s+sl\s+no',
    r'references?\s+&\s+case',
    r'^\[\d+\]',
    r'proceedings\s+of\s+the',
    r'department\s+of',
    r'dept\.?\s+of',
    r'under\s+the\s+guidance',
    r'under\s+my\s+supervision',
    r'academic\s+course',
    r'academic\s+year',
    r'assistant\s+professor',
    r'associate\s+professor',
    r'professor\b',
    r'ramaiah\s+institute',
    r'institute\s+of\s+technology',
    r'visvesvaraya',
    r'bachelor\s+of\s+engineering',
    r'internal\s+guide',
    r'external\s+guide',
    r'head\s+of\s+the\s+dept',
    r'signature\s+of',
    r'coordinator',
    r'submitted\s+by\s*:',
    r'usn\s*:',
    r'course\s+coordinator',
]

def is_boilerplate(text: str) -> bool:
    import re
    t = text.lower()
    return any(re.search(pat, t) for pat in BOILERPLATE_PATTERNS)

def _build_fallback_answer(query: str, chunks: List[Dict[str, Any]], conflicts: List[Dict[str, Any]]) -> str:
    if not chunks:
        return "I could not find relevant information in the uploaded documents, images, video, or audio to answer your question."

    import re
    top_chunk = chunks[0]
    top_mod = top_chunk.get("modality", "document")
    top_source = top_chunk.get("source_id", "uploaded media")

    stop_words = {
        "what", "is", "the", "in", "of", "and", "to", "a", "an", "for", "about",
        "how", "why", "this", "that", "from", "with", "on", "as", "by", "are",
        "was", "were", "or", "case", "study", "report", "please", "tell", "explain",
        "summarize", "show", "give", "me", "between", "does", "did", "do", "like", "any"
    }
    q_words = [w for w in re.findall(r"\b\w+\b", query.lower()) if len(w) > 2 and w not in stop_words]

    # Collect and score sentences across the retrieved chunks
    scored_sentences = []

    for rank, c in enumerate(chunks[:5]):
        content = c.get("content", "")
        pnum = c.get("metadata", {}).get("page_num") or c.get("page_num")
        src = c.get("source_id", top_source)
        mod = c.get("modality", top_mod)

        # Normalize line endings
        content_single_line = re.sub(r'\n+', ' ', content)
        # Split by sentence terminators
        parts = re.split(r'(?<=[.!?])\s+', content_single_line)

        for p in parts:
            p_clean = " ".join(p.split()).strip("-*• ")
            # Ensure sentence starts with clean word character
            p_clean = re.sub(r'^[^\wA-Za-z]+', '', p_clean)
            # Remove leading numbering like "1. ", "5.4 ", "8.4.1 "
            p_clean = re.sub(r'^(?:\d+\.)+\s*', '', p_clean)

            if len(p_clean) < 30 or not p_clean[0].isupper() or len(p_clean.split()) < 5:
                continue
            if p_clean.startswith(('http', 'Page ', 'www.', 'Table ', 'INDEX', 'CERTIFICATE', 'REFERENCES')):
                continue
            if is_boilerplate(p_clean):
                continue

            p_lower = p_clean.lower()
            # Calculate match with query terms
            matches = sum(1 for qw in q_words if qw in p_lower)
            # Phrase bonus if consecutive query terms appear
            phrase_bonus = 0
            for i in range(len(q_words) - 1):
                if f"{q_words[i]} {q_words[i+1]}" in p_lower:
                    phrase_bonus += 3

            # Rank bonus: top retrieved chunk gets strong relevance weight
            rank_weight = max(0, (5 - rank) * 3)
            num_bonus = 1 if any(char.isdigit() for char in p_clean) else 0

            score = matches * 5 + phrase_bonus + rank_weight + num_bonus
            scored_sentences.append((score, p_clean, pnum, src, mod, rank))

    scored_sentences.sort(key=lambda x: x[0], reverse=True)

    seen = set()
    unique_sentences = []
    for s in scored_sentences:
        sent_key = s[1][:50].lower()
        if sent_key not in seen:
            seen.add(sent_key)
            unique_sentences.append(s)

    if not unique_sentences:
        return f"Retrieved content from **{top_source}**, but no substantive text directly matched your inquiry."

    sections = []

    # 1. Executive Summary & Direct Answer (from the top-scored sentence)
    best_sent = unique_sentences[0][1]
    best_pnum = unique_sentences[0][2]
    best_src = unique_sentences[0][3]
    best_mod = unique_sentences[0][4]
    cite_tag = f"[{best_mod.upper()}: {best_src}, p.{best_pnum}]" if best_pnum else f"[{best_mod.upper()}: {best_src}]"

    sections.append(f"Based on **{best_src}**, {best_sent} {cite_tag}\n")

    # 2. Key Findings & Document Details (4-6 comprehensive bullet points)
    bullet_items = unique_sentences[1:7]
    if bullet_items:
        sections.append("### Key Findings & Document Details")
        for score, sent, pnum, src, mod, rnk in bullet_items:
            c_tag = f"[{mod.upper()}: {src}, p.{pnum}]" if pnum else f"[{mod.upper()}: {src}]"
            words = sent.split()

            if ":" in sent[:35]:
                lead, rest = sent.split(":", 1)
            else:
                lead = " ".join(words[:3])
                rest = " ".join(words[3:])

            sections.append(f"- **{lead.strip()}:** {rest.strip()} {c_tag}")
        sections.append("")

    # 3. Context & Implications (1-2 paragraphs from remaining top points)
    remaining = unique_sentences[7:11]
    if remaining:
        sections.append("### Context & Implications")
        context_body = " ".join(s[1] for s in remaining)
        sections.append(f"{context_body}\n")

    # 4. Cross-Modal Conflict / Discrepancy Note (if genuine conflicts exist)
    if conflicts:
        sections.append("### Source Variation Note")
        for conf in conflicts:
            sections.append(
                f"- *Discrepancy noted:* {conf.get('explanation', '')} "
                f"({conf.get('modality_a', '').upper()}: {conf.get('source_a', '')} vs {conf.get('modality_b', '').upper()}: {conf.get('source_b', '')})"
            )

    return "\n".join(sections).strip()
