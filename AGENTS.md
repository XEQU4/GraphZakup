# Instructions for working on GrafZakup

This project is a thesis system for analysing relationships between participants in Kazakhstan's public procurement, with a possible later pilot. Requirements and workflow are in [docs/ROADMAP.md](docs/ROADMAP.md), the target architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and the original findings are in [docs/AUDIT.md](docs/AUDIT.md).

## Workflow and language

- Read the roadmap and documents for the current phase before starting a task. Complete the assigned phase; do not start the next one automatically.
- Distinguish implemented behaviour from proposed designs. Update a phase's status only after meeting its acceptance criteria and checking the result.
- The user runs Git commands. Do not run Git commands, create commits, branches or pull requests, or push changes without a separate instruction.
- Preserve the user's changes. `test.py` contains learning exercises, not application tests. Do not repurpose it for this project.
- Use English for project documentation, instructions, code comments, UI and CLI messages, generated explanations, prompts, and proposed commit messages. Save decisions in the repository so the next task can continue without chat history.
- Develop and verify the English version first. Add Russian website localisation later, after the English interface is complete. Preserve official source labels, identifiers and original data in their source language; translating parser selectors would break data collection.

## Data and safe changes

- Before changing a schema or algorithm that can affect saved data, check for a current backup and verified restoration in [docs/RECOVERY.md](docs/RECOVERY.md).
- Do not run `import_contracts --mode=full`, data cleanup, live parsing, the Celery pipeline, or paid generation to verify refactoring. These require an explicit user instruction. Use fixtures and a separate test database.
- Test migrations and imports on an isolated database. Do not delete the source database or use it for trial restoration.
- Do not put passwords, tokens, `.env`, dumps, or original responses containing personal data in documentation, test fixtures, Git or Docker images. Local backups and reports belong in the ignored `artifacts/` directory.
- Parsers fetch and normalise data; ingestion services own persistence and stage orchestration. Do not add separate orchestration to views or management commands.
- Parse money as `Decimal` from a string. Distinguish a missing result, a temporary source failure, and confirmed absence of a finding.

## Graphs and explanations

- Do not merge people by name alone. Similarity creates a matching candidate with evidence and confidence.
- Relationships must have a source, evidence and temporal applicability. Company debt belongs to the company and is not automatically assigned to its owner.
- Use the same saved evidence for the graph, rules and explanations. A weak shared contact alone does not establish a violation.
- Preserve stable cluster identifiers and version history. Repeated collection without meaningful changes must not recreate the graph or explanation.
- An LLM explains prepared facts and rule results. Entity identity, relationships and scores are computed by verifiable algorithms. Provide a template explanation when the LLM fails.
- GET reads saved results. Start generation and recalculation through authorised background tasks with deduplication and result-version checks.

## Interface and verification

- Phase 4 must substantially improve graph presentation and interaction: readable labels, neighbour highlighting, relationship filters, evidence inspection, convenient navigation and saved layouts.
- The user will provide overall UI/UX references. Do not finalise the site's visual style, palette or Bootstrap replacement before receiving them.
- Verify changed behaviour in every phase. Imports, migrations, identity, graph versions and AI require meaningful tests; syntax checks are not a substitute.
- Do not report checks as successful without running them. Distinguish static analysis, offline tests and live-source checks.
- Report changed behaviour, completed checks and remaining limitations. For environment restrictions, first distinguish a sandbox error from a defect in the project.
