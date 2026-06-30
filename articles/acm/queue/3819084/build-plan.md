# Build Plan — Article to Mini-Repo to CairnStone to Tool Miner

## Phase 1 — Safe acquisition

Create a source artifact from URL metadata and fetch status. Do not store full body unless user supplies permissioned text.

## Phase 2 — Mini-repo scaffold

Write STONEYARD.md, source.json, provenance.json, derived-notes.md, candidates.json, and build-plan.md.

## Phase 3 — CairnStone chain

Stone the mini-repo path into chain `article-acm-queue-3819084`, create orientation, auto-link files, and set the orientation stone as HEAD.

## Phase 4 — Tool mining

Run existing tool miner functions over the chain and source metadata:

- parse_source_for_tool_opportunities
- score_tool_candidates
- generate_blueprint_candidates
- compare_against_toolsmith_inventory
- create_build_plan

## Phase 5 — Toolsmith handoff

Promote high-ranking candidates into build-factory blueprints only after deduplication.
