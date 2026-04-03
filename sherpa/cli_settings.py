from __future__ import annotations

from sherpa.config import Settings, get_settings


def resolve_settings(*, profile: str | None) -> Settings:
    """Merge optional CLI --profile into settings (paper simulation sandbox)."""
    base = get_settings()
    if profile is None or not profile.strip():
        return base
    return base.model_copy(update={"simulation_profile": profile.strip()})
