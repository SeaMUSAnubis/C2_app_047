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


settings = Settings()
