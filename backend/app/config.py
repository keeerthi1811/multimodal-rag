import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
VECTOR_STORAGE_DIR = DATA_DIR / "vectors"
GRAPH_STORAGE_DIR = DATA_DIR / "graph"
UPLOADS_DIR = DATA_DIR / "uploads"

# Ensure directories exist
for d in [DATA_DIR, VECTOR_STORAGE_DIR, GRAPH_STORAGE_DIR, UPLOADS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    # Groq API
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    groq_vision_model: str = Field(default="llama-3.2-11b-vision-preview", alias="GROQ_VISION_MODEL")
    groq_audio_model: str = Field(default="whisper-large-v3-turbo", alias="GROQ_AUDIO_MODEL")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")

    # Weaviate
    weaviate_url: str = Field(default="", alias="WEAVIATE_URL")
    weaviate_api_key: str = Field(default="", alias="WEAVIATE_API_KEY")
    use_local_vector_fallback: bool = Field(default=True, alias="USE_LOCAL_VECTOR_FALLBACK")

    # Models & Modes
    embedding_model: str = Field(default="BAAI/bge-base-en-v1.5", alias="EMBEDDING_MODEL")
    reranker_model: str = Field(default="BAAI/bge-reranker-base", alias="RERANKER_MODEL")
    whisper_mode: str = Field(default="groq", alias="WHISPER_MODE")

    # Storage paths
    data_dir: Path = DATA_DIR
    vector_dir: Path = VECTOR_STORAGE_DIR
    graph_dir: Path = GRAPH_STORAGE_DIR
    uploads_dir: Path = UPLOADS_DIR

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()
