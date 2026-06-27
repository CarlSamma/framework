"""HYDRA V-Genome client — Neo4j 5.x graph of attack techniques.

Regola 2: PostgreSQL is for CHRONOS; Neo4j is HYDRA's graph store.
Regola 5: timeouts on external DB calls.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import UUID

from tap.config import Settings
from tap.logger import get_logger

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger("hydra.v_genome")


class VGenomeClient:
    """Async client for the HYDRA V-Genome (Neo4j)."""

    def __init__(self, settings: Settings) -> None:
        self.uri = settings.hydra_neo4j_uri
        self.user = settings.hydra_neo4j_user
        self.password = settings.hydra_neo4j_password
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Initialize the Neo4j async driver."""
        from neo4j import AsyncGraphDatabase

        async with asyncio.timeout(10.0):
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            await self._driver.verify_connectivity()
        logger.info("v_genome_connected", uri=self.uri)

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def get_techniques(
        self,
        target_model: str,
        asr_threshold: float = 0.6,
        stealth_threshold: float = 0.7,
        burned: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query V-Genome for techniques effective against a target model.

        Args:
            target_model: target model identifier (e.g., 'hackinga0').
            asr_threshold: minimum surrogate ASR.
            stealth_threshold: minimum stealth score.
            burned: include burned techniques.
            limit: max rows.

        Returns:
            List of technique records.
        """
        if self._driver is None:
            raise VGenomeError("V-Genome driver not connected")

        query = """
        MATCH (t:AttackTechnique)-[:TARGETS]->(m:TargetModel {model_id: $target_model})
        WHERE t.asr >= $asr_threshold
          AND t.stealth >= $stealth_threshold
          AND t.burned = $burned
        RETURN t.technique_id AS technique_id,
               t.name AS name,
               t.category AS category,
               t.asr AS asr,
               t.stealth AS stealth,
               t.tags AS tags
        ORDER BY t.asr * t.stealth DESC
        LIMIT $limit
        """
        async with asyncio.timeout(15.0):
            session = self._driver.session()
            try:
                result = await session.run(
                    query,
                    target_model=target_model,
                    asr_threshold=asr_threshold,
                    stealth_threshold=stealth_threshold,
                    burned=burned,
                    limit=limit,
                )
                records = [dict(record.data()) async for record in result]
            finally:
                await session.close()

        logger.info(
            "v_genome_techniques_fetched",
            target_model=target_model,
            count=len(records),
        )
        return records

    async def mark_burned(
        self,
        technique_id: UUID,
        target_model: str,
        evidence: str = "",
    ) -> None:
        """Mark a technique as burned for a target model."""
        if self._driver is None:
            raise VGenomeError("V-Genome driver not connected")

        query = """
        MATCH (t:AttackTechnique {technique_id: $technique_id})
        SET t.burned = true, t.burned_evidence = $evidence
        """
        async with asyncio.timeout(10.0):
            session = self._driver.session()
            try:
                await session.run(
                    query,
                    technique_id=str(technique_id),
                    evidence=evidence,
                )
            finally:
                await session.close()
        logger.info(
            "v_genome_technique_burned",
            technique_id=str(technique_id),
            target_model=target_model,
        )

    async def add_provenance(
        self,
        technique_id: UUID,
        attack_id: UUID,
        outcome: bool,
        asr: float,
    ) -> None:
        """Add provenance edge after CHRONOS extraction completes."""
        if self._driver is None:
            raise VGenomeError("V-Genome driver not connected")

        query = """
        MATCH (t:AttackTechnique {technique_id: $technique_id})
        CREATE (t)-[:PROVENANCE {
            attack_id: $attack_id,
            outcome: $outcome,
            observed_asr: $asr,
            observed_at: datetime()
        }]->(r:Run {id: $attack_id})
        """
        async with asyncio.timeout(10.0):
            session = self._driver.session()
            try:
                await session.run(
                    query,
                    technique_id=str(technique_id),
                    attack_id=str(attack_id),
                    outcome=outcome,
                    asr=asr,
                )
            finally:
                await session.close()
        logger.info(
            "v_genome_provenance_added",
            technique_id=str(technique_id),
            attack_id=str(attack_id),
            outcome=outcome,
        )


class VGenomeError(Exception):
    """Domain error for V-Genome failures."""
