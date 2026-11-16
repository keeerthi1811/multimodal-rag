import re
import json
import logging
from typing import List, Dict, Any, Optional
import numpy as np

from app.config import settings
from app.db.groq_client import groq_wrapper
from app.db.weaviate_client import weaviate_wrapper
from app.db.neo4j_client import neo4j_wrapper

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self._model = None
        self.dim = 768

    def _get_model(self):
        if self._model is None:
            try:
                import socket
                is_online = False
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.4)
                    sock.connect(("1.1.1.1", 53))
                    sock.close()
                    is_online = True
                except Exception:
                    is_online = False

                from sentence_transformers import SentenceTransformer
                if is_online:
                    logger.info(f"Loading embedding model: {settings.embedding_model}")
                    self._model = SentenceTransformer(settings.embedding_model)
                    logger.info("Embedding model loaded successfully.")
                else:
                    try:
                        self._model = SentenceTransformer(settings.embedding_model, local_files_only=True)
                        logger.info("Loaded cached embedding model.")
                    except Exception:
                        logger.info("Offline and model not cached locally. Using deterministic 768-dim embedder.")
                        self._model = "fallback"
            except Exception as e:
                logger.warning(f"Could not load SentenceTransformer '{settings.embedding_model}': {e}. Using deterministic fallback embedder.")
                self._model = "fallback"
        return self._model

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        model = self._get_model()
        if model != "fallback" and model is not None:
            try:
                embeddings = model.encode(texts, normalize_embeddings=True)
                return [emb.tolist() for emb in embeddings]
            except Exception as e:
                logger.warning(f"Embedding encoding failed with model: {e}. Falling back.")

        # Deterministic lightweight fallback embedder (hash projection to unit sphere)
        embeddings = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            words = re.findall(r'\w+', text.lower())
            if not words:
                words = ["empty"]
            for idx, word in enumerate(words):
                h = hash(word) % self.dim
                vec[h] += 1.0 / (idx + 1)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            embeddings.append(vec.tolist())
        return embeddings

    def encode_single(self, text: str) -> List[float]:
        return self.encode([text])[0]

embedding_service = EmbeddingService()

def extract_triples_with_groq(text: str) -> Dict[str, Any]:
    """Uses Groq JSON mode (llama-3.3-70b-versatile) to extract knowledge graph entities and relational triples."""
    if groq_wrapper.is_configured:
        try:
            prompt = f"""
            You are an expert knowledge graph extraction model.
            Extract all key entities and relational triples from the following text.
            Return ONLY valid JSON matching this schema:
            {{
              "entities": [
                {{"name": "Entity Name", "type": "Concept/Organization/Person/Metric/Date/etc."}}
              ],
              "triples": [
                {{"subject": "Entity A", "predicate": "RELATIONSHIP", "object": "Entity B"}}
              ]
            }}

            Text to analyze:
            \"\"\"{text}\"\"\"
            """
            response_str = groq_wrapper.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=settings.groq_model,
                response_format={"type": "json_object"},
                temperature=0.0
            )
            data = json.loads(response_str)
            return {
                "entities": data.get("entities", []),
                "triples": data.get("triples", [])
            }
        except Exception as e:
            logger.warning(f"Groq triple extraction failed: {e}. Using rule-based fallback.")

    # Rule-based fallback extractor for triples
    entities = []
    triples = []
    
    # Extract capitalized multi-word phrases or key words
    candidates = re.findall(r'\b[A-Z][a-zA-Z0-9_-]+(?:\s+[A-Z][a-zA-Z0-9_-]+)*\b', text)
    unique_candidates = list(dict.fromkeys(candidates))
    for c in unique_candidates[:6]:
        entities.append({"name": c, "type": "NamedEntity"})

    # Form basic pairwise relations if 2 or more entities exist
    if len(unique_candidates) >= 2:
        for i in range(len(unique_candidates) - 1):
            triples.append({
                "subject": unique_candidates[i],
                "predicate": "ASSOCIATED_WITH",
                "object": unique_candidates[i+1]
            })
    elif len(unique_candidates) == 1:
        triples.append({
            "subject": unique_candidates[0],
            "predicate": "DESCRIBED_IN",
            "object": "DocumentContext"
        })

    return {"entities": entities, "triples": triples}

def represent_and_store_chunks(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates embeddings, extracts graph triples, and persists to Weaviate and Neo4j."""
    if not chunks:
        return {"chunks_stored": 0, "triples_stored": 0}

    # 1. Generate embeddings and store in Weaviate / local fallback
    texts = [c["content"] for c in chunks]
    embeddings = embedding_service.encode(texts)
    vector_ids = weaviate_wrapper.add_documents(chunks, embeddings)

    # 2. Extract triples and persist in Neo4j / local fallback
    total_triples = 0
    for chunk in chunks:
        extraction = extract_triples_with_groq(chunk["content"])
        triples = extraction.get("triples", [])
        if triples:
            neo4j_wrapper.add_triples(
                triples=triples,
                source_id=chunk["source_id"],
                chunk_id=chunk["chunk_id"],
                modality=chunk["modality"]
            )
            total_triples += len(triples)

    logger.info(f"Stored {len(vector_ids)} chunks into Vector Store and {total_triples} triples into Knowledge Graph.")
    return {
        "chunks_stored": len(vector_ids),
        "triples_stored": total_triples,
        "vector_ids": vector_ids
    }
