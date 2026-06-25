"""Expected Information Gain property selector.

Replaces the static priority list in engine.select_next_property().
Scores each candidate property by:
  EIG(p) = H_residual(p) × yield_rate(p) - cost(p)

Uses math.log2 from stdlib (no numpy dependency).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from tap.config import Settings
from tap.domain.candidate_graph import CandidateGraph
from tap.execution.probe_memory import ProbeMemory
from tap.logger import get_logger

log = get_logger("eig_ranker")


class EIGRanker:
    """Expected Information Gain property selector.

    Scores each candidate property by combining entropy reduction,
    historical yield rate, and transport cost.
    """

    def __init__(
        self,
        candidate_graph: CandidateGraph,
        probe_memory: ProbeMemory,
        settings: Settings,
    ) -> None:
        self._cg = candidate_graph
        self._pm = probe_memory
        self._settings = settings
        self._universe = self._load_universe(settings.eig_property_universe_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def rank(self, unconfirmed_properties: list[str]) -> list[tuple[str, float]]:
        """Return (property_key, eig_score) sorted descending."""
        scored = []
        for prop_key in unconfirmed_properties:
            h_residual = self._universe.get(prop_key, 1.0)
            yield_rate = 0.5  # default for unseen
            # We can't call get_family_yield_rate without a probe text, so
            # use the property key itself as a heuristic lookup
            conn = self._pm._db._ensure_connected()
            cursor = await conn.execute(
                """SELECT AVG(CASE WHEN pattern_class = 'VERIFY_HIT' THEN 1.0 ELSE 0.0 END) as rate
                   FROM probe_memory
                   WHERE probe_preview LIKE ?""",
                (f"%{prop_key}%",),
            )
            row = await cursor.fetchone()
            if row and row["rate"] is not None:
                yield_rate = float(row["rate"])
            cost = 1.0  # fixed for X transport
            eig = h_residual * yield_rate - cost
            scored.append((prop_key, round(eig, 4)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    async def select_next(self) -> str:
        """Return the highest-EIG unconfirmed property."""
        confirmed = await self._cg.get_confirmed_properties()
        confirmed_keys = {p.property_key for p in confirmed}
        all_properties = list(self._universe.keys())
        if not all_properties:
            # Fallback to static list if no universe config
            all_properties = [
                "word_count", "total_length", "first_letter", "language",
                "word1_length", "word2_length", "word1_language", "word2_language",
            ]
        unconfirmed = [k for k in all_properties if k not in confirmed_keys]
        if not unconfirmed:
            return "additional_metadata"
        ranked = await self.rank(unconfirmed)
        if not ranked:
            return unconfirmed[0]
        return ranked[0][0]

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _load_universe(self, path: str) -> dict[str, float]:
        """Load EIG property universe from JSON file.

        Expected format: {"word_count": 2.0, "total_length": 3.0, ...}
        """
        try:
            p = Path(path)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                return {k: float(v) for k, v in data.items()}
        except Exception as e:
            log.warning("eig_universe_load_failed", path=path, error=str(e))
        # Default universe
        return {
            "word_count": 2.0,
            "total_length": 3.0,
            "first_letter": 1.0,
            "language": 1.5,
            "word1_length": 2.0,
            "word2_length": 2.0,
            "word1_language": 1.5,
            "word2_language": 1.5,
        }