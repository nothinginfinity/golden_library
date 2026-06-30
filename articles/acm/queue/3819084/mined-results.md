# Mined Results — ACM Queue 3819084 Article Stoneyard

## Source

- URL: https://queue.acm.org/detail.cfm?id=3819084
- Chain: article-acm-queue-3819084
- HEAD: 03e6ba2c9577c728b8d851ae2272f4f62550dc49aba4497318678dcf9d4529a0
- Repo path: nothinginfinity/golden_library/articles/acm/queue/3819084
- Artifact mode: metadata and derivative tools only

## Tool mining status

The article URL could not be directly fetched by ordinary web fetch because it returned HTTP 403. The full article body was not copied. A copyright-safe mini-repo scaffold was created and stoned instead.

## Created stone chain

CairnStone v5 created 4 source file stones plus orientation, architecture, lint, and review stones.

Primary file stones:

- STONEYARD.md — 287bd55986670b6f1b71f7e8aed2eb63d98852c8228ddc17e3d9cc48f2506f5c
- build-plan.md — 9d3a4e8608cedbf4419de413f60d41d3b8e3fccda5ba9f2db5d664a8179491b3
- candidates.json — 677b294405907a5cfd8748da7c1f462fd8bd5216092133e60baeab2b39fc96b0
- source.json — 09bca7461bf809b7ab5018a97fc6397c71fb92fc3b550c7a9fc78157c6b73406

Orientation HEAD:

- 03e6ba2c9577c728b8d851ae2272f4f62550dc49aba4497318678dcf9d4529a0

## Tool opportunities detected

The tool miner produced 3 evidence-backed MCP candidates from the safe article mini-repo context:

### 1. parse_cairnstone_chain_for_tools

Parse a CairnStone chain manifest and HEAD refs into MCP tool opportunities.

- Category: analysis
- Priority: medium
- Confidence: 0.75
- Effort: small
- Safety risk: low

### 2. extract_existing_mcp_tools

Extract existing MCP tools from code, manifests, and JSON-RPC handlers.

- Category: extraction
- Priority: medium
- Confidence: 0.75
- Effort: small
- Safety risk: low

### 3. generate_mcp_blueprint_candidates

Generate build-factory-compatible MCP blueprint candidates.

- Category: build
- Priority: medium
- Confidence: 0.75
- Effort: medium
- Safety risk: low

## Blueprint generated

Project name:

```text
article-acm-queue-3819084-tools-mcp
```

Namespace:

```text
com.agentfeedoptimization
```

Suggested options:

- auto_status_tool: true
- compatibility_date: 2024-11-01
- execution_logging: true
- r2_payload_offload: false
- vector_embedding: false
- write_receipt: true

Optional secret:

- GITHUB_TOKEN — optional GitHub source expansion token

## Miner tool issues discovered

The direct `mine_cairnstone_chain` call failed because the tool miner attempted `GET /v1/stones?chain=article-acm-queue-3819084&limit=200` and received HTTP 404 from its configured default CairnStone REST endpoint.

The direct CairnStone v5 MCP chain manifest call succeeded, proving the chain exists and is navigable through the v5 MCP.

The following miner helpers returned JavaScript input-shape errors when called with the documented `{ source }` schema:

- score_tool_candidates — `Cannot read properties of undefined (reading 'map')`
- compare_against_toolsmith_inventory — `Cannot read properties of undefined (reading 'filter')`
- create_build_plan — `Cannot read properties of undefined (reading 'map')`

These appear to expect a parsed candidate array internally but do not derive it from `source` before mapping/filtering.

## Recommended next patch

Patch the Tool Miner helper pipeline so these helpers call `parse_source_for_tool_opportunities(source)` first when candidate arrays are missing.

Pseudo-flow:

```text
if (!input.candidates) {
  parsed = parse_source_for_tool_opportunities(input.source)
  candidates = parsed.recommended_tools
}
```

## Product conclusion

Yes: the article-to-mini-repo-to-CairnStone-to-tool-mining loop works, with one important boundary.

For public articles, the safest default is not to store the article body. Store source metadata, fetch status, provenance, derivative notes, candidate tools, and blueprints. If the user supplies permissioned text or the source license allows extraction, that text can be added later as a separate permissioned source stone.
