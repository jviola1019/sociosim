"""Run manifest: everything needed to reproduce a run bit-identically."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import socio_sim
from socio_sim.config import RunConfig


@dataclass
class Manifest:
    config: dict
    config_hash: str
    root_seed: int
    package_version: str
    pack_versions: dict
    content_mode: str
    campaign_specs: list[dict] | None = None
    llm_cache_hash: str | None = None
    stream_hash: str | None = None
    event_count: int | None = None

    @classmethod
    def create(cls, cfg: RunConfig, pack_versions: dict,
               llm_cache_hash: str | None = None,
               campaign_specs: list[dict] | None = None) -> "Manifest":
        return cls(
            config=cfg.to_dict(),
            config_hash=cfg.config_hash(),
            root_seed=cfg.root_seed,
            package_version=socio_sim.__version__,
            pack_versions=dict(pack_versions),
            content_mode=cfg.content_mode,
            campaign_specs=campaign_specs,
            llm_cache_hash=llm_cache_hash,
        )

    def save(self, path: str | Path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.__dict__, indent=2, sort_keys=True),
                     encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def run_config(self) -> RunConfig:
        return RunConfig.from_dict(self.config)

    def campaigns(self):
        from socio_sim.ads.campaigns import campaigns_from_specs
        return campaigns_from_specs(self.campaign_specs)
