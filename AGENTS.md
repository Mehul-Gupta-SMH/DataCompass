# AGENTS.md — Data Compass

Instructions for AI agents working on this project.

---

## Team Roles

| Agent | Role |
|-------|------|
| **Claude Sonnet 4.6** | Developer — implements features, fixes bugs, writes prompt templates |
| **OpenAI Codex (o4-mini)** | Planner + Tester + Git Manager — co-plans features, runs tests, writes commits |
| **Both** | Planning — review backlog, scope tasks, decide approach together before implementation |

---

## Workflow

```
1. Plan      → Both agents review TASK.md backlog and agree on scope + approach
2. Implement → Claude writes the code
3. Test      → Codex runs the test suite, adds missing tests if needed
4. Commit    → Codex makes the git commit (see commit rules below)
5. Log       → Both update TASK.md with final status and notes
```

---

## Codex Responsibilities

### Testing
- After Claude finishes a task, run the full test suite: `pytest tests/`
- If new code paths are uncovered, add tests in `tests/` before committing
- Frontend tests: `npm test` from `frontend/`
- Do NOT commit if any test fails — fix or flag the failure first

### Git Commits
- Stage only files relevant to the completed task (no `.env`, no `*.db`, no `__pycache__`)
- Always include both agents as co-authors:

```
git commit -m "$(cat <<'EOF'
<type>(<scope>): <short description>

<body — what changed and why>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
Co-Authored-By: OpenAI Codex <noreply@openai.com>
EOF
)"
```

- **Never push directly to `master`** — commit to `Claude/Playground/Dev` or a feature branch
- Commit types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`

### Task Logging
- Update `TASK.md` status to `[x]` once tests pass and commit is made
- Add a row to the Change Log with date, branch, file(s), and what changed

---

## Planning Protocol

When the user asks to plan a task:
1. Both agents read the relevant backlog item from `TASK.md`
2. Agree on: files to change, approach, edge cases to test
3. Claude records the agreed plan in `TASK.md` under a `[~]` status row
4. Claude implements; Codex waits and then tests

---

## Git Workflow

- Branch: `Claude/Playground/Dev` (default) or a named feature branch
- Never force-push, never `--no-verify`
- PR to `master` is always done by the human user via GitHub UI

---

## Project Quick Reference

- Backend: `uvicorn backend.app:app --reload` (port 8000)
- Frontend: `npm run dev` from `frontend/` (port 5173)
- Tests: `pytest tests/` from project root
- Config: `Utilities/config.yaml` → `model_config.YAML`, `retrieval_config.YAML`, `database_config.YAML`
- Provider API keys: `APIManager/model_access_config.YAML` (gitignored)