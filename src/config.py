from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "UEBA Endpoint Monitoring"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    database_url: str = Field(
        default="postgresql://ueba:ueba@localhost:5432/ueba",
        alias="DATABASE_URL",
    )
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_expires_minutes: int = Field(default=60 * 8, alias="JWT_EXPIRES_MINUTES")
    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openrouter/free", alias="OPENROUTER_MODEL")
    openrouter_chat_completions_url: str = Field(
        default="https://openrouter.ai/api/v1/chat/completions",
        alias="OPENROUTER_CHAT_COMPLETIONS_URL",
    )
    ocsvm_model_path: str = Field(
        default="weights/ocsvm_cert_r42_chunked.joblib",
        alias="OCSVM_MODEL_PATH",
    )
    ocsvm_model_version: str = Field(
        default="ocsvm-cert-r42-chunked",
        alias="OCSVM_MODEL_VERSION",
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    llm_provider: str = Field(default="openai_compatible", alias="LLM_PROVIDER")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    llm_timeout_seconds: int = Field(default=20, alias="LLM_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    llm_enabled: bool = Field(default=True, alias="LLM_ENABLED")
    llm_prompt_version: str = Field(default="ueba-explanation-v1", alias="LLM_PROMPT_VERSION")


settings = Settings()
