# Code-review-graph (CRG) — All Blue Core

Local-first code intelligence for **smaller, cheaper AI reviews**. Not part of runtime (FastAPI/Next.js). Index stays on your machine in `.code-review-graph/` (gitignored).

**Upstream:** [code-review-graph](https://github.com/tirth8205/code-review-graph)  
**Spec alignment:** `.spec-kit/specs/api/ingestion-oop.spec.md`

---

## One-time setup (per machine)

```powershell
pip install code-review-graph
# or: pipx install code-review-graph

cd C:\Users\Leo Fulgencio\Projects\project-all-blue
code-review-graph install --platform cursor
```

Restart Cursor after `install`.

---

## Build / refresh index

```powershell
cd C:\Users\Leo Fulgencio\Projects\project-all-blue

# First time or after large refactors
code-review-graph build

# Day to day (changed files only)
code-review-graph update
```

Optional background freshness (Cursor has no hooks):

```powershell
code-review-graph watch
# or: crg-daemon add . --alias all-blue && crg-daemon start
```

---

## Token-minimal workflow (required habit)

1. **Do not** paste whole repos or `GRAPH_REPORT`-style dumps into chat.
2. Before a review, run:
   ```powershell
   code-review-graph detect-changes --brief
   ```
   Use `update --brief` only if the graph may be stale (rebase, big merge).
3. In Cursor, ask narrowly: *“Review my diff using the code-review-graph MCP; start with minimal context.”*
4. Prefer MCP tools: `get_minimal_context` → `detect_changes` / `get_impact_radius` → read only listed files.

### Lean MCP tool set (optional)

In Cursor MCP config for `code-review-graph`, limit tools to cut noise:

```json
{
  "mcpServers": {
    "code-review-graph": {
      "command": "code-review-graph",
      "args": [
        "serve",
        "--repo",
        "C:\\Users\\Leo Fulgencio\\Projects\\project-all-blue",
        "--tools",
        "get_minimal_context_tool,detect_changes_tool,get_impact_radius_tool,get_review_context_tool,query_graph_tool"
      ]
    }
  }
}
```

Or environment variable: `CRG_TOOLS=get_minimal_context_tool,detect_changes_tool,get_impact_radius_tool`

---

## Ingestion refactor checks

When reviewing `feat/ingestion-oop-refactor` (or similar):

| Question | CRG helps with |
|----------|----------------|
| What depends on `sync_service.py`? | `get_impact_radius` / `query_graph` |
| Did we break `PropertyListing` consumers? | Blast radius from `models.py` |
| Is router wiring isolated? | Callers of `IngestionOrchestrator` |

Physical truth still requires:

```powershell
cd apps/api-fastapi
.\.venv\Scripts\python.exe scripts\verify_ingestion_v1_v7.py
.\.venv\Scripts\python.exe crawl_test.py --portal remaxrd
```

---

## What CRG does not replace

- `.spec-kit/` — architectural ground truth
- Integration tests / `crawl_test` — Manual Success
- HTTP contract checks (202 / 501 / 400)
- **Graphify** — see [graphify-upgrade-requirements.md](graphify-upgrade-requirements.md). Agents suggest Graphify only when mandatory gates and optional triggers there are met; default stays CRG.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `command not found` | `pipx install code-review-graph` or add Scripts to PATH |
| Stale graph after rebase | `code-review-graph update` or `build` |
| Windows MCP errors | See upstream README — use `.exe` path + `PYTHONUTF8=1` |