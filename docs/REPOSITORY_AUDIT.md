# Repository structure and cleanup, 10 October 2026

The user requested one Compose file, a repository/function usage audit, removal
of unused files including the accidental Next.js starter, and user-operated Git
commands. This is a structural review and regression check. It does not replace
the security/data/AI findings in FINAL_AUDIT.md or certify every function's
semantics. No Git commands, working migrations, source collection or inference
were run for this cleanup.

## Audit method and coverage

- Inventoried maintained source/configuration/documentation, Python ASTs and
  imports, React static/dynamic imports, routes, assets and styles.
- Reviewed Django autodiscovery, AppConfig, models/migrations, admin, management
  commands, Celery registration, compatibility exports and template references.
  A zero ordinary-import count is insufficient evidence for deletion.
- Backend inventory before cleanup: 214 Python modules, 1,156 functions/methods.
  Root/scripts/logging/test review: 22 modules and 139 functions/methods.
- Frontend inventory after cleanup: 134 source/assets, including 71 scripts and
  1,357 function bodies/callbacks. All frontend source modules are reachable from
  application or test entry points.
- Five legacy/API JavaScript files and two CJS test scripts: 215 functions and
  callbacks, parsed with Acorn. Two PowerShell scripts: one named function and
  six script blocks, parsed with PowerShell AST. No parse errors were found.
- Reviewed dependency manifests, generated metadata, current deployment commands
  and dated documentation. Dependencies were retained; advisory remediation is
  separately recorded as AUD-010.

Machine-readable inventories and verified removed-file copies are local under
`artifacts/repository-cleanup/`; no private evidence or dependencies are added to
the repository. The Next.js archive contains 25 source files, not node_modules.

## Resulting layout

The existing Django domain boundaries are retained. Moving models/migrations or
renaming `apps.owners` would require a compatibility/data migration without
improving this task's behavior. Parsers remain separate from persistence and
orchestration. Operational scripts stay in `scripts/`, proxy configuration in
`deploy/`, and cross-domain regressions in `tests/`.

Seven global React stylesheets now live under `frontend/src/styles/`; their
import order is unchanged. Component/page styles remain beside their owners.
`frontend/README.md` documents the frontend boundaries. Root README and
ARCHITECTURE now describe the current application, rather than mixing planned
React/old phase counts with the completed implementation. Historical phase/audit
documents and ARTICLE_CONTEXT retain their dated evidence.

## Removed or consolidated

| Item | Evidence and disposition |
| --- | --- |
| `next-app/` | Separate accidental Next.js starter, no application consumer; explicitly authorised deletion, source archived locally |
| `services/` | Obsolete directory containing only four Python cache files, no source |
| Root `governmentprocurementgraph.egg-info/`, `iz2.egg-info/` | Generated setuptools metadata; active virtual environment distribution metadata retained |
| `apps/contracts/views.py`, `apps/dashboard/admin.py`, `apps/dashboard/models.py` | Empty Django scaffolds with no definitions or registrations |
| `apps/core/utils.py` | Two unconsumed setting wrappers |
| `apps.ai.services.render_explanation` | Unconsumed text-only wrapper; publication uses explanation_content for text and structured document |
| `apps.ingestion.services.Decimal` import | Unused import; parser amount normalization unchanged |
| Orb and old Starfield components/styles | Unreachable components; active Particles implementation retained |
| `static/images/glitch_effect.gif` | No template, style, source or runtime reference |
| `cn`, `getLocale` frontend helpers | Unconsumed exports |
| `.full.yml`, `.server.yml`, `.gpu.yml` Compose overlays | Consolidated into optional profiles in `docker-compose.yml` |

Keep `.venv`, frontend dependencies, IDE preferences, native schedules/logs,
backups, model cache and collected static assets. They have operational/user
purposes even though Git ignores them. Keep legacy Django pages, graph helpers,
all migrations and required licences. Generated package metadata can reappear
after an environment sync; it remains ignored.

## Deployment changes

One Compose file selects CPU Ollama (`local-ai`), NVIDIA Ollama (`local-ai-gpu`)
and Caddy (`https`) through COMPOSE_PROFILES. CPU and GPU are alternatives.
`prepare_deploy.py --ai cpu|gpu|template` writes consistent provider/model settings;
`--domain` and `--acme-email` also write HTTPS/trust/cookie settings. Existing
secrets/environments are never overwritten. Normal startup is:

```sh
docker compose --env-file .env.docker up --build -d
```

Dockerfile remains necessary to build the shared image. Namespaces/volumes and
database identifiers are preserved. The diagnostic web port binds to loopback;
only the optional proxy publishes public ports. The proxy refuses missing HTTPS
security settings before listening.

Real Compose probing found that an optional dependency can allow its dependent
to start after initialization fails. A separate AI-worker startup guard now
checks the configured local model's metadata before consuming tasks. It never
downloads or infers; template mode skips the model check. A missing model fails
startup and the existing restart policy permits recovery once available.
Ingestion remains independent. GPU's internal hostname passes the same local
provider validation as CPU's hostname.

The source snapshot helper now includes frontend/deploy/article files and prunes
generated assets/dependencies before traversal. Test discovery uses explicit
`apps tests` labels, preserving the user's learning `test.py`.

## Verification

- Full isolated PostgreSQL suite: 640 tests passed, zero skips; owned database
  removed. Focused source-inventory, provider/startup and recovery tests included.
- React: 141 tests passed, production build and formatting passed. All generated
  JS/CSS/fonts/HTML/manifest bytes remain identical; only the third-party notice
  drops the removed Orb listing. Full source licences remain.
- Both legacy CJS regression suites passed, including graph/filter/layout and
  safe literal-text/link cases.
- Eight synthetic single-file Compose variants passed; ten real Linux proxy
  configuration guard cases passed. The optional-dependency failure behavior
  was reproduced in two isolated containers and both were removed.
- Native `.env`, learning `test.py`, dependency manifests/locks and article
  context match their pre-task fingerprints.

Runtime verification is recorded below. No source
quality, public-domain certificate, NVIDIA execution or model-quality claim is
made by this structural audit. Preserve the separate limits in FINAL_AUDIT.md
and DEPLOYMENT_CHECK.md.

## Final runtime result

The rebuilt image and single-file base stack started successfully in isolated
project `iz2-cleanup-20261010`. PostgreSQL/Redis/web/both workers/beat became
healthy and migrations completed. The HTTPS profile then started with a local
Caddy CA: 23 HTTP and 23 HTTPS page/API/static reads passed, including frame
protection and secure CSRF cookies. TLS validation used the test CA, not an
insecure bypass. Ten proxy guard cases additionally exercised invalid settings.

An empty, isolated Ollama service returned model-not-found; the real new AI-worker
entrypoint exited before starting Celery. No model pull/inference occurred.
The ordinary template AI worker remained healthy. Runtime UID was 10001 and
the removed files were absent from the image. No working database was mounted.
The collector network was isolated and collection flags/credentials disabled.
Only the owned test project's containers, volumes and networks were removed;
the user's Redis and native services remained. Docker Desktop was started for
these checks and left available.

`.gitattributes` retains LF endings for shell entrypoints on Windows checkouts.
Current Markdown links and the final maintained-file inventory were verified.
GPU hardware execution and a new model-generation run were outside this cleanup;
the earlier CPU inference rehearsal remains in DEPLOYMENT_CHECK.md.
