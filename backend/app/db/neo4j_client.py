import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class LocalDiskGraphStore:
    """Disk-persisted Graph Store fallback when native Neo4j is offline."""
    def __init__(self, storage_path: Path):
        self.storage_file = storage_path / "local_graph.json"
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.nodes = data.get("nodes", {})
                    self.edges = data.get("edges", [])
                logger.info(f"Loaded graph with {len(self.nodes)} nodes and {len(self.edges)} edges from disk.")
            except Exception as e:
                logger.warning(f"Failed to load local graph store: {e}")
                self.nodes = {}
                self.edges = []

    def _save(self):
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump({"nodes": self.nodes, "edges": self.edges}, f)
        except Exception as e:
            logger.error(f"Failed to persist local graph store: {e}")

    def add_node(self, node_id: str, label: str, properties: Dict[str, Any]):
        self.nodes[node_id] = {
            "id": node_id,
            "label": label,
            "properties": properties
        }
        self._save()

    def add_edge(self, source_id: str, target_id: str, relationship: str, properties: Dict[str, Any]):
        # Check if edge already exists
        for edge in self.edges:
            if edge["source"] == source_id and edge["target"] == target_id and edge["relationship"] == relationship:
                edge["properties"].update(properties)
                self._save()
                return
        self.edges.append({
            "source": source_id,
            "target": target_id,
            "relationship": relationship,
            "properties": properties
        })
        self._save()

    def query_neighborhood(self, entity_names: List[str], hops: int = 2) -> Dict[str, Any]:
        """Perform 1-2 hop neighborhood traversal from seed entity names."""
        target_entity_keys = {name.strip().lower() for name in entity_names if name.strip()}
        if not target_entity_keys:
            return {"nodes": [], "edges": []}

        matched_node_ids = set()
        for nid, node in self.nodes.items():
            name = node.get("properties", {}).get("name", nid).lower()
            if name in target_entity_keys or any(tok in name for tok in target_entity_keys):
                matched_node_ids.add(nid)

        active_nodes = set(matched_node_ids)
        result_edges = []

        current_frontier = set(matched_node_ids)
        for _ in range(hops):
            next_frontier = set()
            for edge in self.edges:
                src = edge["source"]
                tgt = edge["target"]
                if src in current_frontier or tgt in current_frontier:
                    if edge not in result_edges:
                        result_edges.append(edge)
                    next_frontier.add(src)
                    next_frontier.add(tgt)
            active_nodes.update(next_frontier)
            current_frontier = next_frontier

        result_nodes = [self.nodes[nid] for nid in active_nodes if nid in self.nodes]
        return {
            "nodes": result_nodes,
            "edges": result_edges
        }

    def get_all(self, limit: int = 150) -> Dict[str, Any]:
        nodes_list = list(self.nodes.values())[:limit]
        node_ids = {n["id"] for n in nodes_list}
        edges_list = [e for e in self.edges if e["source"] in node_ids and e["target"] in node_ids][:limit]
        return {"nodes": nodes_list, "edges": edges_list}

    def delete_source(self, source_id: str) -> int:
        """Deletes all edges and nodes associated with source_id from local store."""
        edges_to_keep = []
        deleted_count = 0
        for edge in self.edges:
            if edge.get("properties", {}).get("source_id") == source_id:
                deleted_count += 1
            else:
                edges_to_keep.append(edge)
        self.edges = edges_to_keep

        connected = set()
        for e in self.edges:
            connected.add(e["source"])
            connected.add(e["target"])

        nodes_to_keep = {}
        for nid, node in self.nodes.items():
            if nid in connected or node.get("properties", {}).get("source_id") != source_id:
                nodes_to_keep[nid] = node
        self.nodes = nodes_to_keep
        self._save()
        return deleted_count

    def clear(self):
        self.nodes = {}
        self.edges = []
        self._save()


class Neo4jClientWrapper:
    def __init__(self):
        self.driver = None
        self.is_connected = False
        self.is_fallback = True
        self.local_store = LocalDiskGraphStore(settings.graph_dir)
        self.init_client()

    def init_client(self):
        try:
            import socket
            from urllib.parse import urlparse
            # Quick 0.5s socket pre-check so tests and startup never hang if Neo4j is offline
            parsed = urlparse(settings.neo4j_uri)
            host = parsed.hostname or "127.0.0.1"
            if host == "localhost":
                host = "127.0.0.1"
            port = parsed.port or 7687
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            conn_res = sock.connect_ex((host, port))
            sock.close()
            if conn_res != 0:
                raise ConnectionError(f"Port {port} on {host} is not open.")

            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                connection_timeout=1.0
            )
            with driver.session() as session:
                session.run("RETURN 1 AS test")
            self.driver = driver
            self.is_connected = True
            self.is_fallback = False
            logger.info(f"Connected to Neo4j database at {settings.neo4j_uri}")
        except Exception as e:
            logger.warning(
                f"Neo4j Desktop/AuraDB not reachable at {settings.neo4j_uri} ({e}). "
                "Local disk-persisted graph store fallback activated."
            )
            self.driver = None
            self.is_connected = True
            self.is_fallback = True

    def add_triples(self, triples: List[Dict[str, Any]], source_id: str, chunk_id: str, modality: str):
        if self.is_fallback or not self.driver:
            for item in triples:
                subj = str(item.get("subject", "")).strip()
                pred = str(item.get("predicate", "RELATED_TO")).strip().replace(" ", "_").upper()
                obj = str(item.get("object", "")).strip()
                if not subj or not obj:
                    continue

                subj_id = f"ent_{subj.lower().replace(' ', '_')}"
                obj_id = f"ent_{obj.lower().replace(' ', '_')}"

                self.local_store.add_node(subj_id, "Entity", {"name": subj, "source_id": source_id, "modality": modality})
                self.local_store.add_node(obj_id, "Entity", {"name": obj, "source_id": source_id, "modality": modality})
                self.local_store.add_edge(subj_id, obj_id, pred, {
                    "source_id": source_id,
                    "chunk_id": chunk_id,
                    "modality": modality,
                    "predicate": pred
                })
            return

        try:
            with self.driver.session() as session:
                for item in triples:
                    subj = str(item.get("subject", "")).strip()
                    pred = str(item.get("predicate", "RELATED_TO")).strip().replace(" ", "_").upper()
                    obj = str(item.get("object", "")).strip()
                    if not subj or not obj:
                        continue
                    query = f"""
                    MERGE (s:Entity {{name: $subject}})
                    ON CREATE SET s.source_id = $source_id, s.modality = $modality
                    MERGE (o:Entity {{name: $object}})
                    ON CREATE SET o.source_id = $source_id, o.modality = $modality
                    MERGE (s)-[r:{pred} {{source_id: $source_id, chunk_id: $chunk_id, modality: $modality}}]->(o)
                    """
                    session.run(query, subject=subj, object=obj, source_id=source_id, chunk_id=chunk_id, modality=modality)
        except Exception as e:
            logger.error(f"Failed to write to Neo4j: {e}. Writing to fallback store.")
            self.local_store_add_triples(triples, source_id, chunk_id, modality)

    def local_store_add_triples(self, triples: List[Dict[str, Any]], source_id: str, chunk_id: str, modality: str):
        for item in triples:
            subj = str(item.get("subject", "")).strip()
            pred = str(item.get("predicate", "RELATED_TO")).strip().replace(" ", "_").upper()
            obj = str(item.get("object", "")).strip()
            if not subj or not obj:
                continue
            subj_id = f"ent_{subj.lower().replace(' ', '_')}"
            obj_id = f"ent_{obj.lower().replace(' ', '_')}"
            self.local_store.add_node(subj_id, "Entity", {"name": subj, "source_id": source_id, "modality": modality})
            self.local_store.add_node(obj_id, "Entity", {"name": obj, "source_id": source_id, "modality": modality})
            self.local_store.add_edge(subj_id, obj_id, pred, {
                "source_id": source_id,
                "chunk_id": chunk_id,
                "modality": modality,
                "predicate": pred
            })

    def query_neighborhood(self, entity_names: List[str], hops: int = 2) -> Dict[str, Any]:
        if self.is_fallback or not self.driver:
            return self.local_store.query_neighborhood(entity_names, hops=hops)

        try:
            with self.driver.session() as session:
                query = """
                MATCH (start:Entity)
                WHERE start.name IN $entity_names
                MATCH path = (start)-[r*1..2]-(target:Entity)
                RETURN nodes(path) AS nodes, relationships(path) AS rels
                LIMIT 50
                """
                result = session.run(query, entity_names=entity_names)
                nodes_dict = {}
                edges_list = []
                for record in result:
                    for node in record["nodes"]:
                        nid = str(node.id)
                        props = dict(node)
                        nodes_dict[nid] = {"id": nid, "label": list(node.labels)[0] if node.labels else "Entity", "properties": props}
                    for rel in record["rels"]:
                        edges_list.append({
                            "source": str(rel.start_node.id),
                            "target": str(rel.end_node.id),
                            "relationship": rel.type,
                            "properties": dict(rel)
                        })
                return {"nodes": list(nodes_dict.values()), "edges": edges_list}
        except Exception as e:
            logger.error(f"Neo4j neighborhood query failed: {e}. Using fallback.")
            return self.local_store.query_neighborhood(entity_names, hops=hops)

    def get_all(self, limit: int = 150) -> Dict[str, Any]:
        if self.is_fallback or not self.driver:
            return self.local_store.get_all(limit=limit)
        try:
            with self.driver.session() as session:
                query = f"""
                MATCH (s)-[r]->(o)
                RETURN s, r, o
                LIMIT {limit}
                """
                result = session.run(query)
                nodes_dict = {}
                edges_list = []
                for record in result:
                    s, r, o = record["s"], record["r"], record["o"]
                    nodes_dict[str(s.id)] = {"id": str(s.id), "label": list(s.labels)[0] if s.labels else "Entity", "properties": dict(s)}
                    nodes_dict[str(o.id)] = {"id": str(o.id), "label": list(o.labels)[0] if o.labels else "Entity", "properties": dict(o)}
                    edges_list.append({
                        "source": str(s.id),
                        "target": str(o.id),
                        "relationship": r.type,
                        "properties": dict(r)
                    })
                return {"nodes": list(nodes_dict.values()), "edges": edges_list}
        except Exception:
            return self.local_store.get_all(limit=limit)

    def delete_source(self, source_id: str) -> int:
        """Deletes all edges and nodes associated with source_id."""
        deleted_count = self.local_store.delete_source(source_id)
        if not self.is_fallback and self.driver:
            try:
                with self.driver.session() as session:
                    session.run("MATCH (n {source_id: $sid}) DETACH DELETE n", sid=source_id)
                    session.run("MATCH ()-[r {source_id: $sid}]->() DELETE r", sid=source_id)
            except Exception as e:
                logger.error(f"Error deleting source from Neo4j: {e}")
        logger.info(f"Deleted {deleted_count} graph elements for source '{source_id}'.")
        return deleted_count

    def clear(self):
        self.local_store.clear()
        if not self.is_fallback and self.driver:
            try:
                with self.driver.session() as session:
                    session.run("MATCH (n) DETACH DELETE n")
            except Exception as e:
                logger.error(f"Error clearing Neo4j: {e}")

neo4j_wrapper = Neo4jClientWrapper()
