import os
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class LocalDiskVectorStore:
    """Automatic disk-persisted vector store fallback with cosine similarity search."""
    def __init__(self, storage_path: Path):
        self.storage_file = storage_path / "local_vectors.json"
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.embeddings: Dict[str, List[float]] = {}
        self._load()

    def _load(self):
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.documents = data.get("documents", {})
                    self.embeddings = data.get("embeddings", {})
                logger.info(f"Loaded {len(self.documents)} vectors from {self.storage_file}")
            except Exception as e:
                logger.warning(f"Failed to load local vector store from {self.storage_file}: {e}")
                self.documents = {}
                self.embeddings = {}

    def _save(self):
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump({"documents": self.documents, "embeddings": self.embeddings}, f)
        except Exception as e:
            logger.error(f"Failed to persist local vector store: {e}")

    def add_documents(self, docs: List[Dict[str, Any]], embs: List[List[float]]) -> List[str]:
        ids = []
        for doc, emb in zip(docs, embs):
            chunk_id = doc.get("chunk_id") or f"chunk_{len(self.documents) + 1}"
            doc["chunk_id"] = chunk_id
            self.documents[chunk_id] = doc
            self.embeddings[chunk_id] = emb
            ids.append(chunk_id)
        self._save()
        return ids

    def search(self, query_emb: List[float], top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.embeddings:
            return []

        q_vec = np.array(query_emb, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        results = []
        for chunk_id, emb in self.embeddings.items():
            doc = self.documents.get(chunk_id, {})
            # Apply filter if provided
            if filters:
                match = True
                for k, v in filters.items():
                    if doc.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            d_vec = np.array(emb, dtype=np.float32)
            d_norm = np.linalg.norm(d_vec)
            if d_norm == 0:
                similarity = 0.0
            else:
                similarity = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))

            res = dict(doc)
            res["score"] = similarity
            results.append(res)

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def count(self) -> int:
        return len(self.documents)

    def delete_source(self, source_id: str) -> int:
        """Deletes all chunks belonging to source_id from local store."""
        deleted_count = 0
        to_del = [cid for cid, doc in self.documents.items() if doc.get("source_id") == source_id]
        for cid in to_del:
            self.documents.pop(cid, None)
            self.embeddings.pop(cid, None)
            deleted_count += 1
        self._save()
        return deleted_count

    def clear(self):
        self.documents = {}
        self.embeddings = {}
        self._save()


class WeaviateClientWrapper:
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.is_fallback = True
        self.local_store = LocalDiskVectorStore(settings.vector_dir)
        self.collection_name = "MultimodalEvidence"
        self.init_client()

    def init_client(self):
        url = settings.weaviate_url.strip()
        api_key = settings.weaviate_api_key.strip()

        if url:
            try:
                import weaviate
                from weaviate.classes.init import Auth
                auth_credentials = Auth.api_key(api_key) if api_key else None
                self.client = weaviate.connect_to_weaviate_cloud(
                    cluster_url=url,
                    auth_credentials=auth_credentials
                )
                self.is_connected = True
                self.is_fallback = False
                logger.info(f"Connected to Weaviate Cloud at {url}")
                self._ensure_schema()
                return
            except Exception as e:
                logger.warning(f"Could not connect to Weaviate at {url}: {e}. Activating local fallback.")

        logger.info("Using local disk-persisted vector store fallback (Windows native / offline safe).")
        self.is_connected = True
        self.is_fallback = True

    def _ensure_schema(self):
        if not self.is_fallback and self.client:
            try:
                collections = self.client.collections.list_all()
                if self.collection_name not in collections:
                    import weaviate.classes.config as wvc
                    self.client.collections.create(
                        name=self.collection_name,
                        vectorizer_config=wvc.Configure.Vectorizer.none(),
                        properties=[
                            wvc.Property(name="chunk_id", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="source_id", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="modality", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="content", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="metadata_json", data_type=wvc.DataType.TEXT),
                        ]
                    )
            except Exception as e:
                logger.error(f"Error checking/creating Weaviate collection: {e}")

    def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]) -> List[str]:
        if self.is_fallback or not self.client:
            return self.local_store.add_documents(documents, embeddings)

        ids = []
        try:
            collection = self.client.collections.get(self.collection_name)
            with collection.batch.dynamic() as batch:
                for doc, emb in zip(documents, embeddings):
                    chunk_id = doc.get("chunk_id")
                    batch.add_object(
                        properties={
                            "chunk_id": chunk_id,
                            "source_id": doc.get("source_id", ""),
                            "modality": doc.get("modality", ""),
                            "content": doc.get("content", ""),
                            "metadata_json": json.dumps(doc),
                        },
                        vector=emb
                    )
                    ids.append(chunk_id)
            return ids
        except Exception as e:
            logger.error(f"Weaviate batch insert failed: {e}. Falling back to local store.")
            return self.local_store.add_documents(documents, embeddings)

    def search(self, query_embedding: List[float], top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if self.is_fallback or not self.client:
            return self.local_store.search(query_embedding, top_k=top_k, filters=filters)

        try:
            collection = self.client.collections.get(self.collection_name)
            response = collection.query.near_vector(
                near_vector=query_embedding,
                limit=top_k,
                return_metadata=["distance"]
            )
            results = []
            for obj in response.objects:
                meta = json.loads(obj.properties.get("metadata_json", "{}"))
                # Distance to similarity: 1 - distance
                distance = obj.metadata.distance if obj.metadata and obj.metadata.distance is not None else 0.5
                score = max(0.0, 1.0 - distance)
                meta["score"] = score
                results.append(meta)
            return results
        except Exception as e:
            logger.error(f"Weaviate query failed: {e}. Falling back to local store.")
            return self.local_store.search(query_embedding, top_k=top_k, filters=filters)

    def count(self) -> int:
        if self.is_fallback or not self.client:
            return self.local_store.count()
        try:
            collection = self.client.collections.get(self.collection_name)
            agg = collection.aggregate.over_all(total_count=True)
            return agg.total_count or 0
        except Exception:
            return self.local_store.count()

    def delete_source(self, source_id: str) -> int:
        """Deletes all chunks belonging to source_id from vector store."""
        deleted_count = self.local_store.delete_source(source_id)
        if not self.is_fallback and self.client:
            try:
                import weaviate.classes.query as wq
                collection = self.client.collections.get(self.collection_name)
                collection.data.delete_many(
                    where=wq.Filter.by_property("source_id").equal(source_id)
                )
            except Exception as e:
                logger.error(f"Error deleting from Weaviate Cloud: {e}")
        logger.info(f"Deleted {deleted_count} vector chunks for source '{source_id}'.")
        return deleted_count

    def clear(self):
        self.local_store.clear()
        if not self.is_fallback and self.client:
            try:
                self.client.collections.delete(self.collection_name)
                self._ensure_schema()
            except Exception as e:
                logger.error(f"Error clearing Weaviate: {e}")

weaviate_wrapper = WeaviateClientWrapper()
