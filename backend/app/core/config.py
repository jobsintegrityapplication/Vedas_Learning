from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    app_name: str = "Vedas Learning"
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    frontend_base_url: str = "http://127.0.0.1:8080"

    database_url: str = "postgresql+psycopg://veda:veda@localhost:5432/veda"
    redis_url: str = "redis://localhost:6379/0"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@veda-learning.local"
    smtp_starttls: bool = False

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "veda-audio"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = False

    content_path: str = "../content/rigveda_lessons.json"
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    email_verification_ttl_seconds: int = 86400

    admin_email: str = "admin@veda-learning.local"
    admin_password: str = "ChangeThisAdminPassword1"
    admin_name: str = "Guru Admin"

    evaluation_engine: str = "none"
    evaluation_engine_version: str = "0"
    alignment_engine: str = "none"
    alignment_engine_version: str = "0"
    pronunciation_engine: str = "none"
    pronunciation_engine_version: str = "0"
    evaluation_test_mode: bool = False
    development_guru_reference_dir: str = ""
    word_match_pass_threshold_percent: float = Field(default=90.0, ge=0, le=100)
    svara_engine: str = "none"
    svara_engine_version: str = "0"
    sanskrit_asr_enabled: bool = False
    pronunciation_evaluation_enabled: bool = False
    gop_enabled: bool = False
    vedic_accent_evaluation_enabled: bool = False
    sanskrit_asr_model_dir: str = ""
    sanskrit_aligner_model_path: str = ""
    sanskrit_aligner_vocab_path: str = ""
    audio_sample_rate: int = Field(default=16000, ge=8000, le=48000)
    model_device: str = "cpu"
    model_cache_dir: str = "./data/models"
    model_num_threads: int = Field(default=2, ge=1, le=16)
    evaluation_fixture_dir: str = ""
    audio_store: str = "s3"
    expose_dev_otp: bool = False
    max_upload_bytes: int = 15_728_640
    min_audio_bytes: int = 64
    min_audio_duration_ms: int = 50
    s3_public_endpoint_url: str = ""
    log_level: str = "INFO"
    log_format: str = "text"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() in {"development", "dev", "local", "test"}

    def validate_runtime_secrets(self) -> None:
        if self.is_dev:
            return
        weak = {"dev-only-change-me", "change-me-to-a-long-random-string", "ChangeThisAdminPassword1", "veda"}
        if self.secret_key in weak or len(self.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be set to a strong value outside local environments")
        if self.admin_password in weak:
            raise RuntimeError("ADMIN_PASSWORD must be changed outside local environments")
        if "://veda:veda@" in self.database_url or self.s3_access_key == "minioadmin":
            raise RuntimeError("Default database or object-storage credentials are not allowed outside local environments")


@lru_cache
def get_settings() -> Settings:
    return Settings()
