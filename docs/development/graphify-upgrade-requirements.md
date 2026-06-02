# Graphify upgrade requirements (All Blue Core)

**Current default:** [code-review-graph (CRG)](code-review-graph.md) for token-minimal diff reviews.

**Upgrade target:** [Graphify](https://github.com/safishamsi/graphify) (`graphifyy` on PyPI) — unified knowledge graph (code + docs + optional SQL/PDF/video), `GRAPH_REPORT.md`, PR triage, team-shared `graphify-out/`.

Agents must **not** install Graphify unless the human approves after this checklist.

---

## When to suggest an upgrade

Suggest migrating from CRG → Graphify only when:

1. **All mandatory gates** (below) are satisfied, **and**
2. **At least two** optional triggers (below) are true for the current task or sprint.

Phrase the suggestion as a short proposal: gaps CRG cannot cover, triggers matched, install steps, and token/disk tradeoff.

---

## Mandatory gates (all required)

| # | Requirement | How to verify |
|---|-------------|---------------|
| M1 | **Human approval** | User explicitly agrees to Graphify install, index build, and possible API use for doc/PDF extraction |
| M2 | **Python 3.10+** | `python --version` |
| M3 | **CLI on PATH** | Prefer `uv tool install graphifyy` or `pipx install graphifyy` (avoid bare `pip` on Windows per upstream) |
| M4 | **Disk & git policy** | Team accepts `graphify-out/` in repo (or a documented subset); `.gitignore` excludes `manifest.json` / `cost.json` per Graphify docs |
| M5 | **CRG baseline exists** | CRG already installed and at least one successful `code-review-graph build` for this repo (proves local graph workflow works before a heavier tool) |
| M6 | **No hotspot block** | High-bandwidth install/index only after user confirms if on metered/hotspot connection |

---

## Optional triggers (need ≥ 2)

| # | Trigger | Why CRG is insufficient |
|---|---------|-------------------------|
| T1 | **Cross-surface architecture** | Single review must span `apps/api-fastapi` + `apps/storefront-next` + `.spec-kit/` + SQL schema with relationship queries, not file-local blast radius |
| T2 | **Non-code artifacts** | PDFs, Office docs, images, videos, or papers must sit in the same graph as application code |
| T3 | **SQL / infra in graph** | Postgres schema, MCP configs, or shell/Docker definitions must be linked to Python/TS call paths |
| T4 | **Team-shared map** | Multiple developers need the same committed `graphify-out/` and `graphify hook install` merge driver |
| T5 | **PR operations** | Need `graphify prs`, triage, or community-based merge-order / impact analysis |
| T6 | **Semantic “why” mining** | Repeated need for design rationale, `# WHY:` / docstring nodes, or “surprising connections” across modules (CRG is structural, not semantic-rich) |
| T7 | **Global / multi-repo graph** | `graphify global` or merging graphs across related repositories |
| T8 | **Token budget explicitly increased** | User states they prefer richer `GRAPH_REPORT.md` / wiki exports over minimal MCP context |
| T9 | **CRG repeated misses** | ≥ 3 review cycles where `get_impact_radius` / `query_graph` failed to surface dependencies that later broke tests or contracts |

---

## Stay on CRG when

- Review is **diff-scoped** (feature branch, single module, ingestion refactor).
- Goal is **low token cost** and fast `detect-changes --brief`.
- Only Python/TS under `apps/` needs impact radius.
- User has not approved Graphify install or `graphify-out/` commit policy.

---

## Approved upgrade path (after gates)

Run only after **M1** approval:

```powershell
# Install (prefer uv)
uv tool install graphifyy
# Optional extras: graphifyy[sql] graphifyy[mcp] graphifyy[office]

cd C:\Users\Leo Fulgencio\Projects\project-all-blue
graphify .                    # PowerShell: no leading slash
graphify cursor install --project
graphify hook install         # optional: post-commit rebuild + graph.json merge driver
```

Add `.graphifyignore` (mirror `.code-review-graphignore` patterns: `node_modules/`, `.venv/`, dist, caches).

**Coexistence:** CRG can remain for day-to-day small reviews; Graphify for architecture/PR/onboarding. Do not duplicate full-repo pastes in chat from either tool.

**Rollback:** `graphify uninstall --project` and remove committed `graphify-out/` only if the team agrees.

---

## Comparison (decision aid)

| Dimension | CRG (default) | Graphify (upgrade) |
|-----------|---------------|-------------------|
| Primary goal | Minimal tokens on **changed** code | Rich **whole-project** knowledge map |
| Index location | `.code-review-graph/` (gitignored) | `graphify-out/` (often committed) |
| Best for | Pre-commit / feature reviews | Onboarding, cross-app design, PR triage |
| Typical chat use | MCP minimal context + a few files | `graphify query`, scoped reads; avoid dumping full report |
| Install size | Moderate pip package | Larger; optional extras (video, office, neo4j) |

---

## Agent checklist (copy into review)

```
[ ] Read graphify-upgrade-requirements.md
[ ] Mandatory gates M1–M6 satisfied
[ ] Count optional triggers (need ≥ 2)
[ ] If yes → propose upgrade to human; if no → use CRG only
[ ] Never install graphifyy without explicit user approval in the same session
```