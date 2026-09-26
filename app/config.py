"""Central settings — every module reads config through here, never os.environ directly."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App / Server
    app_env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # LLM / Synthesis
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 800
    llm_timeout_seconds: int = 20
    llm_fallback_model: str | None = None

    # Local LLM path (optional)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3"

    # Embeddings & Retrieval
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    faiss_index_path: str = "indexes/faiss.index"
    bm25_index_path: str = "indexes/bm25.pkl"
    chunks_path: str = "data/chunks.jsonl"
    top_k_dense: int = 10
    top_k_sparse: int = 10
    rrf_k: int = 60

    # Corpus / Data Paths
    corpus_dir: str = "corpus/"
    data_dir: str = "data/"
    indexes_dir: str = "indexes/"

    # Controller
    controller_min_tokens: int = 6
    controller_stability_window_ms: int = 400
    controller_llm_fallback_enabled: bool = False

    # Streaming
    stream_chunk_interval_ms: int = 800

    # Session
    session_db_path: str = "data/sessions.db"
    session_ttl_seconds: int = 3600

    # Telemetry
    telemetry_log_path: str = "logs/events.jsonl"
    telemetry_log_format: str = "json"

    # Evaluation
    eval_fixtures_dir: str = "app/evaluation/fixtures/"
    eval_g2_target: float = 0.80
    eval_g3_target: float = 0.70
    eval_g4_target: float = 0.85


settings = Settings()
