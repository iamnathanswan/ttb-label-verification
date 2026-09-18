"""Runtime settings.

Limits exist to protect a publicly reachable endpoint with a funded API key
behind it (OPS-05), without refusing the workload the tool was built for (BAT-02).
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sarah: "big importers who dump 200, 300 label applications on us at once."
PEAK_BATCH_MULTIPLIER = 2


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    # Org-scoped keys must name a workspace; workspace-scoped keys need not.
    anthropic_workspace_id: str = ""
    # Chosen on measured latency, not cost: Opus 5 missed the PRF-01 budget at
    # 5,590 ms; Sonnet 5 meets it at 4,220 ms with identical accuracy on the
    # discriminating typographic fixtures. See docs/perf.md.
    anthropic_model: str = "claude-sonnet-5"

    max_upload_bytes: int = 10 * 1024 * 1024
    max_batch_files: int = 300          # BAT-02
    # Per-file limits alone allow 300 x 10 MB to be held at once. This caps
    # what one submission can materialise in memory.
    max_batch_bytes: int = 400 * 1024 * 1024
    extraction_concurrency: int = 8     # BAT-06

    # OPS-05 — ceiling on a public endpoint with a funded key behind it.
    # Left unset, it is derived from max_batch_files so the two cannot drift
    # apart: a ceiling below the advertised batch size would reject the peak
    # submission this tool was built to absorb, and would do so on the first
    # real use rather than in testing.
    rate_limit_labels: int | None = None
    rate_limit_window_seconds: int = 900

    # PRF-04 — downscale before the model call
    max_image_edge_px: int = 1600

    @model_validator(mode="after")
    def _derive_rate_limit(self) -> "Settings":
        if self.rate_limit_labels is None:
            self.rate_limit_labels = self.max_batch_files * PEAK_BATCH_MULTIPLIER
        return self

    @model_validator(mode="after")
    def _reject_contradictory_limits(self) -> "Settings":
        if self.rate_limit_labels < self.max_batch_files:
            raise ValueError(
                f"rate_limit_labels ({self.rate_limit_labels}) is below max_batch_files "
                f"({self.max_batch_files}): a full batch would be rejected by the rate limit."
            )
        return self


settings = Settings()
