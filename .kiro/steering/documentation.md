---
inclusion: always
---

# Documentation

All project docs live in `docs/`. Index: `docs/architecture.md`, `docs/api-design.md`, `docs/database-design.md`, `docs/project-management/decision-log.md`, `docs/architecture/architecture-decisions.md`.

## Update Requirements

Update docs in the same change when you alter:

- APIs: `docs/api-design.md` and the relevant `docs/api/*.md`.
- Schemas, migrations, or RLS: `docs/database-design.md` and `docs/database/*.md`.
- Workflows, SMS statuses, AI features, or architecture: matching `docs/architecture/*.md`, `docs/design/user-journeys.md`.
- Requirements or scope: `docs/prd.md`, `docs/frs.md`, `docs/nfrs.md`, `docs/roadmap.md`.
- Env vars or setup: `docs/deployment/environment-configuration.md`, `local-development.md`.

If code contradicts docs, resolve it by updating one of them. Do not leave them inconsistent.

## Conventions

- Markdown, one H1 per file, concise headings, tables for reference data, fenced code blocks with language tags.
- Use relative links. Write in the project's language (British spelling is used in existing docs).
- Document the why, not just the what. Remove stale content instead of annotating it.
- Never put secrets or real phone numbers in docs. Use placeholders.

## README Maintenance

Keep `README.md` current with: project description and non-affiliation notice, setup and run steps, environment variables, test commands, simulation vs live mode explanation, and links to `docs/`.

## Architecture Decision Records

- Record significant decisions (new library, boundary change, provider choice, data model shift) as ADRs in `docs/architecture/architecture-decisions.md` and log them in `docs/project-management/decision-log.md`.
- ADR format: title, status, context, decision, consequences, alternatives considered.
- Supersede rather than rewrite old ADRs.
