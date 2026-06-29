"""
Seed script — V-Genome Neo4j (branch hybrid)
=============================================
Popola Neo4j con:
  1. Constraints e index (da v_genome_schema.cypher)
  2. Nodi TargetModel, DefenseLayer, AttackTechnique
  3. Relazioni TARGETS, COUNTERS, COMPLEMENTS

Uso:
    python scripts/seed_vgenome.py

Variabili .env usate:
    HYDRA_NEO4J_URI      (default: bolt://localhost:7687)
    HYDRA_NEO4J_USER     (default: neo4j)
    HYDRA_NEO4J_PASSWORD (default: tapv4hydra)
"""
from __future__ import annotations

import asyncio
import os
import sys

# Aggiunge src/ al path per importare tap.config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("HYDRA_NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("HYDRA_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("HYDRA_NEO4J_PASSWORD", "tapv4hydra")


# ---------------------------------------------------------------------------
# Queries — allineate esattamente a v_genome_schema.cypher
# ---------------------------------------------------------------------------

CONSTRAINTS = [
    "CREATE CONSTRAINT attack_technique_id IF NOT EXISTS FOR (t:AttackTechnique) REQUIRE t.technique_id IS UNIQUE",
    "CREATE CONSTRAINT target_model_id IF NOT EXISTS FOR (m:TargetModel) REQUIRE m.model_id IS UNIQUE",
    "CREATE CONSTRAINT defense_layer_id IF NOT EXISTS FOR (d:DefenseLayer) REQUIRE d.layer_id IS UNIQUE",
    "CREATE INDEX technique_burned IF NOT EXISTS FOR (t:AttackTechnique) ON (t.burned)",
    "CREATE INDEX technique_asr IF NOT EXISTS FOR (t:AttackTechnique) ON (t.asr)",
    "CREATE INDEX technique_stealth IF NOT EXISTS FOR (t:AttackTechnique) ON (t.stealth)",
]

SEED_NODES = """
MERGE (:TargetModel { model_id: "hackinga0", name: "@HackingA0", platform: "twitter" });

MERGE (:DefenseLayer { layer_id: "input_filter",       name: "Input Filter" });
MERGE (:DefenseLayer { layer_id: "alignment",          name: "Model Alignment" });
MERGE (:DefenseLayer { layer_id: "output_moderation",  name: "Output Moderation" });

MERGE (t:AttackTechnique { technique_id: "crescendo" })
  ON CREATE SET
    t.name       = "Crescendo / Foot-in-the-Door",
    t.category   = "incremental",
    t.asr        = 0.62,
    t.stealth    = 0.78,
    t.burned     = false,
    t.cost_usd   = 0.04,
    t.avg_turns  = 4.0,
    t.tags       = ["persuasion", "multi-turn"];

MERGE (t:AttackTechnique { technique_id: "pap_authority" })
  ON CREATE SET
    t.name       = "Psychological Authority Persuasion",
    t.category   = "persuasion",
    t.asr        = 0.55,
    t.stealth    = 0.71,
    t.burned     = false,
    t.cost_usd   = 0.03,
    t.avg_turns  = 2.5,
    t.tags       = ["pap", "authority"];

MERGE (t:AttackTechnique { technique_id: "roleplay_persona" })
  ON CREATE SET
    t.name       = "Roleplay Persona Hijack",
    t.category   = "roleplay",
    t.asr        = 0.68,
    t.stealth    = 0.74,
    t.burned     = false,
    t.cost_usd   = 0.05,
    t.avg_turns  = 3.0,
    t.tags       = ["persona", "roleplay", "multi-turn"];

MERGE (t:AttackTechnique { technique_id: "many_shot" })
  ON CREATE SET
    t.name       = "Many-Shot Priming",
    t.category   = "priming",
    t.asr        = 0.71,
    t.stealth    = 0.65,
    t.burned     = false,
    t.cost_usd   = 0.08,
    t.avg_turns  = 1.0,
    t.tags       = ["few-shot", "priming"];

MERGE (t:AttackTechnique { technique_id: "prompt_injection" })
  ON CREATE SET
    t.name       = "Prompt Injection via Context",
    t.category   = "injection",
    t.asr        = 0.58,
    t.stealth    = 0.80,
    t.burned     = false,
    t.cost_usd   = 0.02,
    t.avg_turns  = 2.0,
    t.tags       = ["injection", "context-manipulation"];
"""

SEED_RELATIONS = """
MATCH (t:AttackTechnique {technique_id: "crescendo"}),
      (m:TargetModel {model_id: "hackinga0"})
MERGE (t)-[r:TARGETS]->(m)
  ON CREATE SET r.asr = 0.62, r.stealth = 0.78, r.observed_at = datetime();

MATCH (t:AttackTechnique {technique_id: "pap_authority"}),
      (m:TargetModel {model_id: "hackinga0"})
MERGE (t)-[r:TARGETS]->(m)
  ON CREATE SET r.asr = 0.55, r.stealth = 0.71, r.observed_at = datetime();

MATCH (t:AttackTechnique {technique_id: "roleplay_persona"}),
      (m:TargetModel {model_id: "hackinga0"})
MERGE (t)-[r:TARGETS]->(m)
  ON CREATE SET r.asr = 0.68, r.stealth = 0.74, r.observed_at = datetime();

MATCH (t:AttackTechnique {technique_id: "many_shot"}),
      (m:TargetModel {model_id: "hackinga0"})
MERGE (t)-[r:TARGETS]->(m)
  ON CREATE SET r.asr = 0.71, r.stealth = 0.65, r.observed_at = datetime();

MATCH (t:AttackTechnique {technique_id: "prompt_injection"}),
      (m:TargetModel {model_id: "hackinga0"})
MERGE (t)-[r:TARGETS]->(m)
  ON CREATE SET r.asr = 0.58, r.stealth = 0.80, r.observed_at = datetime();

MATCH (t:AttackTechnique {technique_id: "crescendo"}),
      (d:DefenseLayer {layer_id: "alignment"})
MERGE (t)-[r:COUNTERS]->(d)
  ON CREATE SET r.evidence = "gradual escalation detected", r.observed_at = datetime();

MATCH (t:AttackTechnique {technique_id: "many_shot"}),
      (d:DefenseLayer {layer_id: "input_filter"})
MERGE (t)-[r:COUNTERS]->(d)
  ON CREATE SET r.evidence = "token flooding bypasses input filter", r.observed_at = datetime();

MATCH (a:AttackTechnique {technique_id: "crescendo"}),
      (b:AttackTechnique {technique_id: "pap_authority"})
MERGE (a)-[r:COMPLEMENTS]->(b)
  ON CREATE SET r.strength = 0.85;

MATCH (a:AttackTechnique {technique_id: "roleplay_persona"}),
      (b:AttackTechnique {technique_id: "many_shot"})
MERGE (a)-[r:COMPLEMENTS]->(b)
  ON CREATE SET r.strength = 0.72;
"""


async def seed() -> None:
    from neo4j import AsyncGraphDatabase

    print(f"[seed_vgenome] Connessione a {NEO4J_URI} ...")
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        await driver.verify_connectivity()
        print("[seed_vgenome] ✅ Connesso a Neo4j")

        async with driver.session() as session:
            # 1. Constraints e index
            print("[seed_vgenome] Creazione constraints e index...")
            for stmt in CONSTRAINTS:
                await session.run(stmt)
            print(f"[seed_vgenome] ✅ {len(CONSTRAINTS)} constraints/index applicati")

            # 2. Nodi (usa MERGE per idempotenza — rieseguibile senza duplicati)
            print("[seed_vgenome] Inserimento nodi (TargetModel, DefenseLayer, AttackTechnique)...")
            for stmt in [s.strip() for s in SEED_NODES.strip().split(";") if s.strip()]:
                await session.run(stmt)
            print("[seed_vgenome] ✅ Nodi inseriti")

            # 3. Relazioni
            print("[seed_vgenome] Inserimento relazioni (TARGETS, COUNTERS, COMPLEMENTS)...")
            for stmt in [s.strip() for s in SEED_RELATIONS.strip().split(";") if s.strip()]:
                await session.run(stmt)
            print("[seed_vgenome] ✅ Relazioni inserite")

        print()
        print("[seed_vgenome] 🌱 V-Genome seed completato con successo!")
        print("[seed_vgenome] Apri Neo4j Browser su http://localhost:7474")
        print("[seed_vgenome] Login: neo4j / tapv4hydra")
        print("[seed_vgenome] Query di verifica:")
        print("[seed_vgenome]   MATCH (t:AttackTechnique)-[:TARGETS]->(m:TargetModel) RETURN t,m")

    except Exception as e:
        print(f"[seed_vgenome] ❌ ERRORE: {e}")
        print("[seed_vgenome] Assicurati che Neo4j sia attivo: docker compose -f docker-compose.infra.yml up -d")
        sys.exit(1)
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(seed())
