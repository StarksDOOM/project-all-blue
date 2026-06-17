# All Blue Core — Token-Efficient Subagents Manual

This manual documents the suite of specialized, token-efficient subagents created to assist with development, issue tracking, regression checking, and structural code reviews in the **All Blue Core** codebase. 

All subagents are configured to utilize the local `code-review-graph` (CRG) index and `.spec-kit` specifications, minimizing context size and bandwidth.

---

## Subagent Suite Overview

### 1. `issue-monitor`
* **Purpose**: Automatically scans open GitHub issues via the `gh` CLI, reads their checklists, scans local git logs to verify completion, and updates or closes issues on GitHub.
* **Token Optimization**: Avoids checking out full source files. Operates on issue text summaries, git logs, and branch diff names.
* **When to use**: To check the status of outstanding roadmap features, verify completed work on GitHub Projects (Kanban), and clean up closed tasks.

### 2. `feature-developer`
* **Role**: The core coding subagent. Implements spec files (`.spec-kit/specs/`) in Python (strict OOP + PEP 257) or TypeScript.
* **Token Optimization**:
  - Uses the CRG index to locate only the exact files requiring edits.
  - Avoids opening entire files by fetching targeted line ranges (`StartLine`/`EndLine`).
  - Limits edits strictly to the minimal requirements (no "while I'm here" refactors).
* **When to use**: When starting implementation of a new spec, fixing a bug in an isolated class, or creating a new component.

### 3. `regression-checker`
* **Role**: Pre-commit guard. Scans modified code in git diffs for stray secrets, dead links, and naked placeholder comments. Enforces pre-commit gates.
* **Token Optimization**: Focuses review strictly on git diff changes and executes targeted pytest paths instead of running full tests.
* **When to use**: Before staging and committing any changes (`git add` / `git commit`).

### 4. `code-reviewer`
* **Role**: Structural graph reviewer and security auditor.
* **Token Optimization**: Resolves import maps, caller/callee relationships, and inheritance chains through structural CRG graph queries instead of reading parent files.
* **When to use**: After completing code changes on a feature branch to analyze blast radius and review security constraints (OWASP Top 10) before merging to `develop`.

---

## Best Practices for Token-Efficient Delegations

When delegating tasks to these subagents, keep instructions narrow and refer to local resources:

1. **Supply File Links**: Always supply exact markdown links in prompts (e.g., `[feature.spec.md](file:///c:/Users/Leo%20Fulgencio/Projects/project-all-blue/.spec-kit/specs/api/feature.spec.md)`).
2. **Point to CRG**: Instruct the subagents to check the graph state first:
   ```text
   "Use the code-review-graph status to ensure the index is built, then query children_of to identify dependencies."
   ```
3. **Isolate Scope**: Explicitly define what is out of scope to prevent the subagent from scanning unrelated directories.
4. **Use Cron Schedules**: You can schedule the `issue-monitor` or `regression-checker` using the `schedule` tool to run tasks periodically:
   - Example prompt for scheduling:
     ```text
     "Invoke the issue-monitor subagent to scan open tasks and update GitHub."
     ```

---

## Related Documentation
* **[Agent Operating Manual](agent-operating-manual.md)**
* **[Engineering Directives](engineering-directives.md)**
* **[Code Review Graph](code-review-graph.md)**
