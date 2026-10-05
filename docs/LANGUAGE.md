# English project baseline

Date: 5 October 2026. Language maintenance after Phase 2; no additional development phase was started.

## User instruction

Use English for all project deliverables, including earlier phase records. Develop the English website first; add Russian website localisation later. This overrides the previous instruction to write technical documents in Russian. The persistent rule is in [AGENTS.md](../AGENTS.md), with later localisation recorded in [ROADMAP.md](ROADMAP.md).

## Changed behaviour

- README, deployment instructions, repository rules, architecture, audit, roadmap, recovery, baseline, and Phase 1-2 records use English. The article context is translated with an explicit historical checkpoint; its earlier test counts/data observations are not presented as a new audit.
- Navigation, pages, search states, graph labels/tooltips, CLI help/errors, logging messages, comments, and docstrings use English.
- HTML declares `lang="en"`; Django explicitly uses `LANGUAGE_CODE="en-us"`. Project display spelling is GrafZakup; repository and external links are preserved.
- The deterministic explanation template and inactive OpenRouter prompt produce/request English. No LLM was enabled or called.
- Runtime ingestion status/candidate labels and the customer-link label use English. `graph.0004_english_display_labels` and `ingestion.0005_english_display_labels` record these label changes without changing stored codes. Existing migrations are untouched.

Apply the prepared migrations in the intended environment using the existing [backup/upgrade procedure](RECOVERY.md):

```powershell
uv run python manage.py migrate
```

If migrations were already applied before this translation finished, repeat the command to record the two new display-label migrations. Docker applies them through its `migrate` service on the next upgraded startup.

## Deliberately preserved source-language content

Official HTML labels/selectors, address parsing vocabulary, contact validation patterns, source-status comparisons, and corresponding HTML fixtures retain their source language. They identify actual external inputs; translating them would break parsing. Russian sample values in regression tests exercise Unicode handling and retention of legacy text. `test.py` remains the user's educational file.

Original company/person names, source values, saved cluster names, and stored explanations were not translated in the working database. GET continues reading saved results without generation or writes. Future localisation must distinguish UI translations from source data and use the explanation language in version/reuse keys.

## Executed verification

| Check | Result |
| --- | --- |
| Existing Django suite, isolated in-memory SQLite | 128 discovered: 126 passed, two PostgreSQL concurrency tests skipped |
| JavaScript regressions | Three searches escape source text/reject obsolete responses; tooltip text remains literal |
| Additional offline language smoke checks | Three passed: seven page types rendered in English, English explanation retains original Unicode facts, GET preserves a Russian saved explanation without generation/writes |
| Models versus migrations | `makemigrations --check --dry-run`: no changes |
| New migration SQL on SQLite | All three field-label changes reported `(no-op)` |
| Documentation | English text and local links/heading anchors checked |
| Python syntax | 141 application/configuration/utility/test files parsed successfully |
| Protected user files | `test.py`, `pyproject.toml`, `uv.lock` SHA-256 match the original baseline |

Local originals, one-off verification scripts, and `verification.json` are in ignored `artifacts/language/`. The working database was not accessed or migrated for this task. No live collection, Celery pipeline, or paid generation ran. PostgreSQL concurrency/Compose were not rerun for translation; their earlier Phase 1-2 protocols remain separate.

Russian website localisation, redesigned graph, KGD, DRF, and React remain future roadmap work. This translation does not change phase completion statuses or approve a visual style.
