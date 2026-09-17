"""Runtime settings. Limits exist to protect a publicly reachable endpoint (OPS-05)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    # Org-scoped keys must name a workspace; workspace-scoped keys need not.
    anthropic_workspace_id: str = ""
    # Chosen on measured latency, not cost: Opus 5 missed the PRF-01 budget at
    # 5,590 ms; Sonnet 5 meets it at 4,220 ms with identical accuracy on the
    # discriminating typographic fixtures. See docs/perf.md.
    anthropic_model: str = "claude-sonnet-5"

    # OPS-05 — public endpoint with a funded key behind it
    max_upload_bytes: int = 10 * 1024 * 1024
    max_batch_files: int = 300  # BAT-02
    extraction_concurrency: int = 8  # BAT-06

    # PRF-04 — downscale before the model call
    max_image_edge_px: int = 1600


settings = Settings()
