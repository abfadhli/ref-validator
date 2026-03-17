"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    unpaywall_email: str = ""
    semantic_scholar_api_key: str = ""

    extraction_model: str = "claude-sonnet-4-6"
    verification_model: str = "claude-sonnet-4-6"

    # API source toggles
    use_crossref: bool = True
    use_semantic_scholar: bool = True
    use_openalex: bool = True
    use_google_scholar: bool = False
    use_arxiv: bool = True

    # User-supplied reference PDFs directory
    refs_dir: str = ""

    concurrency: int = 5
    api_timeout: float = 30.0
    api_retries: int = 3
    fuzzy_title_threshold: float = 0.85
