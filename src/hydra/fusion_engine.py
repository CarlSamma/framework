"""HYDRA Fusion Engine — Python stub for feature-level fusion.

The canonical implementation is a Rust crate; this module provides a
Python-only fallback that composes techniques, applies pruning, and returns
FusedPrompt candidates.
"""
from __future__ import annotations

import itertools
from typing import Any

from shared.models import FusedPrompt, PlatformConstraint, TechniqueRef


class CartesianPruningFusionEngine:
    """Generate and prune fused prompt candidates from technique sets."""

    def __init__(self, max_combo_size: int = 3, feature_dim: int = 128) -> None:
        if max_combo_size < 1:
            raise ValueError("max_combo_size must be >= 1")
        self.max_combo_size = max_combo_size
        self.feature_dim = feature_dim

    def generate_payloads(
        self,
        techniques: list[dict[str, Any]],
        platform: PlatformConstraint = PlatformConstraint.TWITTER_280,
        top_k: int = 5,
    ) -> list[FusedPrompt]:
        """Generate top-K fused prompts from a list of technique records.

        Args:
            techniques: list of dicts with keys {technique_id, name, category, asr, stealth, tags}.
            platform: target platform constraint.
            top_k: number of candidates to return.

        Returns:
            List of FusedPrompt candidates.
        """
        candidates: list[FusedPrompt] = []
        for r in range(1, self.max_combo_size + 1):
            for combo in itertools.combinations(techniques, r):
                fused = self._fuse(combo, platform)
                candidates.append(fused)

        candidates.sort(key=lambda p: p.expected_asr * p.expected_stealth, reverse=True)
        return candidates[:top_k]

    def _fuse(self, combo: tuple[dict[str, Any], ...], platform: PlatformConstraint) -> FusedPrompt:
        """Merge a subset of techniques into a single FusedPrompt."""
        composition = [
            TechniqueRef(
                technique_id=tech.get("technique_id", f"tech-{i}"),
                name=tech.get("name", "unknown"),
                weight_in_fusion=1.0 / len(combo),
            )
            for i, tech in enumerate(combo)
        ]

        # Weighted average of technique metrics by their asr/stealth.
        total_weight = sum(1.0 for _ in combo) or 1.0
        asr = sum(tech.get("asr", 0.5) for tech in combo) / total_weight
        stealth = sum(tech.get("stealth", 0.5) for tech in combo) / total_weight

        # Build a simple feature vector seeded by technique ids.
        feature_vector = self._build_feature_vector(combo)

        # Compose prompt text from technique names.
        prompt_text = " + ".join(tech.get("name", "?") for tech in combo)

        return FusedPrompt(
            prompt_text=prompt_text,
            feature_vector=feature_vector,
            expected_asr=float(asr),
            expected_stealth=float(stealth),
            composition=composition,
            obfuscation_layers=[],
            m2s_converted=(platform == PlatformConstraint.TWITTER_280),
            platform_native_format=platform,
            estimated_cost_usd=0.05 * len(combo),
        )

    def _build_feature_vector(self, combo: tuple[dict[str, Any], ...]) -> list[float]:
        """Hash technique ids into a fixed-size vector."""
        vector = [0.0] * self.feature_dim
        for tech in combo:
            tech_id = str(tech.get("technique_id", ""))
            if not tech_id:
                continue
            for i, ch in enumerate(tech_id):
                idx = (i * 7 + ord(ch)) % self.feature_dim
                vector[idx] = (vector[idx] + 1.0) / 2.0  # dampen average
        return vector
