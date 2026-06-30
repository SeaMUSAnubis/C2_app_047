from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "UEBA Endpoint Monitoring"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    database_url: str = Field(
        default="postgresql://ueba_user:ueba_password@localhost:5432/ueba_db",
        alias="DATABASE_URL",
    )
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_expires_minutes: int = Field(default=60 * 8, alias="JWT_EXPIRES_MINUTES")
    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    mistral_model: str = Field(default="mistral-small-latest", alias="MISTRAL_MODEL")
    mistral_chat_completions_url: str = Field(
        default="https://api.mistral.ai/v1/chat/completions",
        alias="MISTRAL_CHAT_COMPLETIONS_URL",
    )
    ocsvm_model_path: str = Field(
        default="src/ml/weights/ocsvm_cert_r42_chunked.joblib",
        alias="OCSVM_MODEL_PATH",
    )
    ocsvm_model_version: str = Field(
        default="ocsvm-cert-r42-chunked",
        alias="OCSVM_MODEL_VERSION",
    )
    ml_model_path: str = Field(default="src/ml/weights", alias="ML_MODEL_PATH")
    ml_artifact_path: str = Field(default="artifacts", alias="ML_ARTIFACT_PATH")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    agent_enrollment_token_ttl_minutes: int = Field(
        default=60, alias="AGENT_ENROLLMENT_TOKEN_TTL_MINUTES"
    )
    agent_heartbeat_timeout_minutes: int = Field(
        default=10, alias="AGENT_HEARTBEAT_TIMEOUT_MINUTES"
    )
    agent_default_sampling_rate: int = Field(
        default=100, alias="AGENT_DEFAULT_SAMPLING_RATE"
    )
    normalizer_enabled: bool = Field(default=True, alias="NORMALIZER_ENABLED")
    normalizer_poll_interval_seconds: float = Field(
        default=10.0, alias="NORMALIZER_POLL_INTERVAL_SECONDS"
    )
    normalizer_batch_size: int = Field(default=200, alias="NORMALIZER_BATCH_SIZE")
    normalizer_run_on_startup: bool = Field(
        default=True, alias="NORMALIZER_RUN_ON_STARTUP"
    )
    ml_scoring_enabled: bool = Field(default=True, alias="ML_SCORING_ENABLED")
    ml_scoring_window_minutes: int = Field(
        default=60 * 24, alias="ML_SCORING_WINDOW_MINUTES"
    )
    ml_scoring_user_batch_size: int = Field(
        default=20, alias="ML_SCORING_USER_BATCH_SIZE"
    )
    ml_scoring_max_users_per_run: int = Field(
        default=50, alias="ML_SCORING_MAX_USERS_PER_RUN"
    )
    ml_scoring_alert_min_risk: int = Field(
        default=60, alias="ML_SCORING_ALERT_MIN_RISK"
    )
    # Phase A.0 (PLAN_LLM.md) — DB connection pool.
    db_pool_min_size: int = Field(default=2, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=20, alias="DB_POOL_MAX_SIZE")
    db_pool_acquire_timeout_seconds: float = Field(
        default=5.0, alias="DB_POOL_ACQUIRE_TIMEOUT_SECONDS"
    )
    db_statement_timeout_read_ms: int = Field(
        default=5000, alias="DB_STATEMENT_TIMEOUT_READ_MS"
    )
    db_statement_timeout_write_ms: int = Field(
        default=30000, alias="DB_STATEMENT_TIMEOUT_WRITE_MS"
    )
    db_statement_timeout_streaming_ms: int = Field(
        default=0, alias="DB_STATEMENT_TIMEOUT_STREAMING_MS"
    )
    db_idle_in_transaction_timeout_ms: int = Field(
        default=10000, alias="DB_IDLE_IN_TRANSACTION_TIMEOUT_MS"
    )
    # Phase 3 (PLAN_LLM.md) — LLM core settings.
    llm_provider: str = Field(default="mistral", alias="LLM_PROVIDER")
    llm_chat_model: str = Field(default="mistral-small-latest", alias="LLM_CHAT_MODEL")
    llm_embedding_model: str = Field(default="mistral-embed", alias="LLM_EMBEDDING_MODEL")
    llm_openai_api_key: str = Field(default="", alias="LLM_OPENAI_API_KEY")
    llm_openai_base_url: str = Field(default="", alias="LLM_OPENAI_BASE_URL")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    llm_timeout_seconds: float = Field(default=30.0, alias="LLM_TIMEOUT_SECONDS")
    llm_chat_enabled: bool = Field(default=True, alias="LLM_CHAT_ENABLED")
    llm_default_language: str = Field(default="vi", alias="LLM_DEFAULT_LANGUAGE")
    llm_cost_currency: str = Field(default="USD", alias="LLM_COST_CURRENCY")
    llm_input_cost_per_1m_tokens: float = Field(
        default=0.0, alias="LLM_INPUT_COST_PER_1M_TOKENS"
    )
    llm_output_cost_per_1m_tokens: float = Field(
        default=0.0, alias="LLM_OUTPUT_COST_PER_1M_TOKENS"
    )
    llm_chat_max_context_messages: int = Field(
        default=20, alias="LLM_CHAT_MAX_CONTEXT_MESSAGES"
    )
    llm_memory_enabled: bool = Field(default=True, alias="LLM_MEMORY_ENABLED")
    llm_memory_semantic_enabled: bool = Field(
        default=False, alias="LLM_MEMORY_SEMANTIC_ENABLED"
    )
    llm_memory_max_retrieve: int = Field(default=5, alias="LLM_MEMORY_MAX_RETRIEVE")
    llm_memory_decay_days: int = Field(default=90, alias="LLM_MEMORY_DECAY_DAYS")
    llm_memory_auto_feedback: bool = Field(
        default=True, alias="LLM_MEMORY_AUTO_FEEDBACK"
    )


settings = Settings()
