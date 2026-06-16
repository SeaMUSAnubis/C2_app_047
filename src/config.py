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
    mistral_model: str = Field(default="mistral-small-latest", alias="MISTRAL_MODEL")
    mistral_chat_completions_url: str = Field(
        default="https://api.mistral.ai/v1/chat/completions",
        alias="MISTRAL_CHAT_COMPLETIONS_URL",
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


settings = Settings()
