# Project All Blue Guidelines

> [!CAUTION]
> **CRITICAL PRE-FLIGHT**: BEFORE making any changes, proposing implementation plans, running terminal commands, or writing code, all agents MUST open and read [REGRESSIONS.md](file:///c:/Users/Leo%20Fulgencio/Projects/project-all-blue/memories/REGRESSIONS.md) in full to prevent environment, cache, or routing regressions.

For all agent rules, refer to:
- [Agents.md](file:///c:/Users/Leo%20Fulgencio/Projects/project-all-blue/Agents.md) (gitignored local overrides)
- [agent-operating-manual.md](file:///c:/Users/Leo%20Fulgencio/Projects/project-all-blue/docs/development/agent-operating-manual.md) (committed canonical copy)

## Commands
- Run FastAPI backend tests: `cd apps/api-fastapi; .\.venv\Scripts\python.exe -m pytest`
- Run Storefront frontend tests: `cd apps/storefront-next; npm test`
- Check TypeScript storefront compilation: `cd apps/storefront-next; npx tsc --noEmit`
