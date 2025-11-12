import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "off", "no"}


@dataclass(frozen=True)
class Settings:
    SECRET_KEY: str
    OPENAI_API_KEY: str | None
    DATABASE_URL: str | None
    AWS_ACCESS_KEY_ID: str | None
    AWS_SECRET_ACCESS_KEY: str | None
    AWS_S3_BUCKET_NAME: str | None
    AWS_SQS_QUEUE_URL: str | None
    JOB_QUEUE_PROVIDER: str
    JOB_POLL_INTERVAL_SECONDS: float
    AI_MAX_RETRIES: int
    AI_RETRY_BACKOFF_BASE: float
    AI_RETRY_BACKOFF_CAP: float
    CONTENT_FILTER_ENABLED: bool
    CONTENT_FILTER_EXTRA_WORDS_PATH: str | None
    PRIVACY_DEFAULT_ANONYMIZED: bool
    MIN_INITIAL_ANALYSIS_WORDS: int
    MIN_UPDATE_ANALYSIS_WORDS: int


def get_settings() -> Settings:
    return Settings(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-insecure-key"),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        DATABASE_URL=os.getenv("DATABASE_URL"),
        AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID"),
        AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY"),
        AWS_S3_BUCKET_NAME=os.getenv("AWS_S3_BUCKET_NAME"),
        AWS_SQS_QUEUE_URL=os.getenv("AWS_SQS_QUEUE_URL"),
        JOB_QUEUE_PROVIDER=os.getenv("JOB_QUEUE_PROVIDER", "inmemory"),
        JOB_POLL_INTERVAL_SECONDS=float(os.getenv("JOB_POLL_INTERVAL_SECONDS", "3.0")),
        AI_MAX_RETRIES=int(os.getenv("AI_MAX_RETRIES", "3")),
        AI_RETRY_BACKOFF_BASE=float(os.getenv("AI_RETRY_BACKOFF_BASE", "1.5")),
        AI_RETRY_BACKOFF_CAP=float(os.getenv("AI_RETRY_BACKOFF_CAP", "30")),
        CONTENT_FILTER_ENABLED=_env_bool("CONTENT_FILTER_ENABLED", True),
        CONTENT_FILTER_EXTRA_WORDS_PATH=os.getenv("CONTENT_FILTER_EXTRA_WORDS_PATH"),
        PRIVACY_DEFAULT_ANONYMIZED=_env_bool("PRIVACY_DEFAULT_ANONYMIZED", False),
        MIN_INITIAL_ANALYSIS_WORDS=int(os.getenv("MIN_INITIAL_ANALYSIS_WORDS", "200")),
        MIN_UPDATE_ANALYSIS_WORDS=int(os.getenv("MIN_UPDATE_ANALYSIS_WORDS", "100")),
    )

