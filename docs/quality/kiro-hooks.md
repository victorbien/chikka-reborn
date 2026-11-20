# Kiro Hooks and Development Automation

**Project:** Chikka Reborn
**Status:** Configured. Hooks load at the next Kiro session start. The scripts were verified by simulating Kiro's calls; the hooks have not yet been observed firing inside Kiro.
**Last Revised:** November 2026

## 1. Purpose and approach

The hooks help Kiro follow the project's steering rules (`.kiro/steering/`): architecture, coding standards, testing, security and documentation. They do three things: check files when they are saved, report what they found at the next prompt, and stop or ask before consequential actions.

Everything uses events Kiro supports: `PostFileSave`, `PostFileCreate`, `PostFileDelete`, `PreToolUse`, `UserPromptSubmit` and `PostTaskExec`, with `command` actions (a shell command that receives JSON on stdin) and `agent` actions (a prompt added to the context). Definitions are in `.kiro/hooks/*.json`. The logic is in `scripts/hooks/` so it can be run, tested and reviewed like any other code.

### How findings reach Kiro

Kiro forwards a command hook's output only for `SessionStart`, `UserPromptSubmit` and `PreToolUse`. A save hook therefore cannot talk to the agent directly. The design is:

```
file saved ──> command hook runs a check ──> writes .kiro/hook-reports/<check>/<file>.json (git-ignored)
next prompt ─> UserPromptSubmit hook re-checks files with open findings ──> prints what is still open
                                                                            (Kiro reads it as context)
```

Findings that were fixed disappear on the next prompt. Nothing is shown when the project is clean. Reports contain the rule, file, line and a message, never the text that matched, so a detected secret is not copied into a second file.

Agent hooks are used only where an agent turn is wanted and rare: when a new service, router or feature is created, and when a spec task finishes.

### What the hooks never do

No hook edits a file, formats code, runs a migration, deploys, sends an SMS, changes credentials or moves money. Report hooks only read. The two safety hooks only allow, ask or block.

## 2. Hook reference

| ID (`.kiro/hooks/<id>.json`) | Trigger and matcher | Action | Purpose |
|---|---|---|---|
| `quality-python-on-save` | PostFileSave `backend/(app\|tests)/**/*.py` | command `quality` | `ruff check`, `ruff format --check`, `mypy app` (strict, as configured in `backend/pyproject.toml`) |
| `quality-frontend-on-save` | PostFileSave `frontend/src/**/*.ts(x)` | command `quality` | `eslint`, `prettier --check` on the file, `tsc --noEmit` for the project |
| `tests-on-save` | PostFileSave backend `*service*.py`, `*router*.py`, `services/*.py`; frontend `features/**/*.ts(x)` | command `tests` | Services: any test referencing the module, unit tests present. Routers: response schema or return type, typed request input, a test that calls each path. Features: a test file exists and mentions the component |
| `new-code-test-review` | PostFileCreate: new backend service or router, new `features/**/*.tsx` | **agent** | Kiro runs the tests check and proposes a test plan per `testing.md`. It asks before writing any test |
| `docs-api-contract-on-save` | PostFileSave `modules/*/*router*.py`, `schemas.py` | command `docs` | Names the affected `docs/api/*.md` and `docs/api-design.md`, and lists routes that no API document mentions |
| `docs-database-on-save`, `docs-database-on-create` | PostFileSave / PostFileCreate `supabase/migrations/*.sql` | command `docs` | Names database documents to review, tables missing from `docs/database/`, policy or grant changes (`row-level-security.md` and an allowed/denied SQL test), and a missing entry in `database-migrations.md` |
| `docs-requirements-on-save` | PostFileSave `docs/prd.md`, `frs.md`, `nfrs.md`, `docs/product/frs/*`, functional and non-functional requirements | command `docs` | Names acceptance-criteria, test-catalogue and traceability documents, and lists requirement IDs in the diff that those documents do not mention |
| `security-scan-on-save` | PostFileSave source, SQL, scripts, docs and `.example` files | command `security` | Credential-shaped values, secret-like assignments, phone-number literals and sensitive values in log calls, unverified webhook routes or providers, routes without `CurrentUserDep`/`ActiveUserDep`/`AdminUserDep`, authenticated handlers that never use the user, frontend `dangerouslySetInnerHTML`, `eval`, tokens in web storage |
| `architecture-on-save` | PostFileSave `backend/app/**/*.py`, `frontend/src/**/*.ts(x)` | command `architecture` | Circular dependencies between modules and files, vendor SDKs outside `app/integrations`, concrete providers imported by services (stricter for chat and SMS), cross-module repository imports, upward dependencies, HTTP types in services, frontend feature-to-feature imports and direct `fetch`. Hints: duplicated function bodies, very long or branching functions |
| `safety-guard-file-writes` | PreToolUse `fs_write`, `str_replace`, `fs_append`, `delete_file` | command `guard-write` | **Blocks** (exit 2) content that looks like a credential, except in test files. **Asks** before changing real `.env` files, committed migrations, `.kiro/hooks`, `.kiro/steering` or `scripts/hooks` |
| `safety-guard-shell-and-mcp` | PreToolUse `execute_pwsh`, `control_pwsh_process`, `tool_call` | command `guard-shell` | **Asks** before: destructive SQL, `supabase db push/reset`, `psql`; deployments and `git push`; calls to the Twilio API, `SMS_PROVIDER_MODE=live`, provider activation; changes to production secrets (`vercel env`, `fly secrets`, `gh secret`, `aws iam`); payment tools and credit adjustments; forced recursive deletes (build folders are exempt); `git reset --hard` and similar; GitHub write tools and AWS-changing MCP tools |
| `findings-summary-on-prompt` | UserPromptSubmit | command `summary` | Re-checks files with open findings and prints those still open (errors and warnings; `info` is hidden). Prints nothing when clean |
| `forget-deleted-file-findings` | PostFileDelete | command `forget` | Removes stored findings of a deleted file |
| `post-task-review` | PostTaskExec | **agent** | After a spec task, runs every check on the changed files and reports real findings and the documents to update |

Severity: `error` should be fixed before the work is finished, `warn` should be looked at, `info` is a hint and is never shown at the prompt.

## 3. Running the checks by hand

Requires the backend virtual environment (`backend\.venv`) and, for the frontend part of `quality`, `frontend\node_modules`. From the repository root:

```powershell
scripts\hooks\run.ps1 all --all --print                 # every check on the whole project
scripts\hooks\run.ps1 all --changed --print             # only files git reports as changed
scripts\hooks\run.ps1 security --paths backend/app/modules/sms/router.py --print
scripts\hooks\run.ps1 quality --paths backend/app/core/config.py --print
scripts\hooks\run.ps1 architecture --print
scripts\hooks\run.ps1 summary                           # what Kiro would see at the next prompt
scripts\hooks\run.ps1 tests --all --print --strict      # exit 1 on an error (usable in CI)
```

Checks: `quality`, `tests`, `docs`, `security`, `architecture`, `all`, `summary`, `forget`, `guard-write`, `guard-shell`.

Simulate Kiro calling a hook, including the JSON on stdin and the exit code:

```powershell
scripts\hooks\tests\simulate-hook.ps1 -Check guard-shell -Command "git push origin main"   # asks
scripts\hooks\tests\simulate-hook.ps1 -Check guard-write -File backend/.env -Text "X=1"    # asks
scripts\hooks\tests\simulate-hook.ps1 -Check quality -File backend/app/core/config.py
```

Run the tests for the hooks themselves:

```powershell
backend\.venv\Scripts\python.exe -m pytest scripts/hooks/tests -q
```

## 4. Baselines (existing findings)

The first run found problems that already existed. They are recorded in `scripts/hooks/baselines/<check>.json` so that only **new** problems are reported. This is a deliberate trade-off: the old problems are not hidden from the project, only from the per-save noise. The list at the time of writing:

| Check | Accepted findings | Worth fixing first |
|---|---|---|
| architecture | 1 circular module dependency, 1 concrete provider import, 9 cross-module internals, 7 feature-to-feature imports, 10 long functions, 2 duplicates | `auth` and `profiles` import each other (`auth/service.py`, `profiles/service.py`). `sms/admin_service.py` imports the concrete `MockSmsProvider`. `chat/repository.py`, `contacts/repository.py` and others import another module's models or repository |
| tests | 2 services without tests, 2 without unit tests, 7 routes no test names, 1 feature without a test file, 53 components not named in a test | `audit` service and `health_service` have no tests; the `system` frontend feature has none |
| docs | 11 routes not found in `docs/api` | The 9 `/admin/sms/*` routes and the 2 `/webhooks/{provider}/*` routes do not appear in `docs/api` (check whether they are documented under another notation, then document them) |
| security | 2 authenticated handlers that never use the user | `GET /sms/countries` and `/sms/capability` are reference data for any signed-in user. Confirm that is intended |

After you fix something, regenerate with `scripts\hooks\run.ps1 <check> --all --update-baseline` and review the diff of the JSON. Never regenerate a baseline to silence a new finding without reading it. "Review this document" reminders are never baselined.

## 5. Changing the rules

- Public routes (no authentication on purpose) are listed in `scripts/hooks/security.py` (`PUBLIC_ROUTE_FILES`, `PUBLIC_ROUTE_FUNCTIONS`). Add one only with a reason in the commit.
- Allowed provider locations are `COMPOSITION_ROOTS` in `architecture.py`.
- Credential patterns are `CREDENTIAL_PATTERNS` in `security.py`; the write guard uses the same list.
- Dangerous-command patterns are `SHELL_RULES` and `MCP_RULES` in `guards.py`.
- Edits to `scripts/hooks/` and `.kiro/hooks/` themselves trigger an "ask", so a change to the safety rules is a visible decision.
- To turn one hook off, remove its file from `.kiro/hooks/` or disable it in Kiro's Agent Hooks panel. Do not disable the two safety hooks without approval.

## 6. Limitations

- **Unverified inside Kiro.** Kiro documents that command hooks get JSON on stdin but not its field names. The scripts therefore look at every string value for a project file path, and fall back to the files git reports as changed. If hooks seem not to fire, check that the matcher regex matches the path format Kiro supplies (relative or absolute). All patterns are written to match anywhere in the path. Hooks start at the next session.
- **Reports appear one prompt late.** A save hook cannot message the agent; the summary hook does, at the next prompt. If nothing is prompted, nothing is shown.
- **Latency.** Each command starts PowerShell and Python (about 1 to 2 seconds). A Python save runs `mypy app`, a TypeScript save runs `tsc --noEmit` (several seconds each). The two safety hooks add that startup time to every file write and shell call.
- **Heuristics, not proof.** "Has a test" means a test file names the module or route, not that behaviour is covered; use `pytest --cov` and `vitest --coverage` for that. Secret detection matches known formats and secret-looking assignments and will miss other values. Webhook, authentication and authorisation checks are structural (a dependency is present, a signature function is referenced, the user is used) and cannot judge correctness. Duplicate detection only finds structurally identical functions. "Unnecessary complexity" is limited to size and branch-count hints.
- **Guards are not a security boundary.** They match patterns in tool requests. A reworded command, a script that runs a command internally, or a person in a terminal is not stopped. They exist to keep the agent from taking consequential steps without a human decision. An "ask" depends on Kiro's handling of the decision, and a hook that fails to start (for example a missing virtual environment) lets the action proceed, because only exit 2 blocks.
- **Windows and PowerShell.** The commands call `powershell` and `backend\.venv\Scripts\python.exe`. Other platforms need a different launcher.
- **Scope.** Unsupported file types are skipped. Generated and vendor folders (`node_modules`, `.venv`, `dist`) are ignored.
- **No financial or SMS tooling exists in the hooks.** The guards recognise attempts; the application's own controls (simulation by default, `SMS_LIVE_CONFIRMED`, administrator activation, rate limits) remain the real protection.

## 7. Files

| Path | Role |
|---|---|
| `.kiro/hooks/*.json` | Hook definitions (15) |
| `scripts/hooks/run.ps1` | Launcher: finds Python, passes stdin through |
| `scripts/hooks/hookcheck.py` | Command line entry and `summary` |
| `scripts/hooks/{quality,testcov,docimpact,security,architecture,guards}.py` | The checks |
| `scripts/hooks/{common,routes}.py` | Shared helpers and the FastAPI route reader |
| `scripts/hooks/baselines/*.json` | Accepted existing findings |
| `scripts/hooks/tests/` | Tests and `simulate-hook.ps1` |
| `.kiro/hook-reports/` | Generated, git-ignored findings |
