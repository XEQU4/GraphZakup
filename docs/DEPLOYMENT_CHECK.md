# Linux deployment preparation, 10 October 2026

The user authorised Linux Docker preparation without selecting a host. This
follow-up implements operational configuration and rehearses it locally; it does
not publish the site or close all findings in FINAL_AUDIT.md. Use DEPLOY.md for
current startup, transfer, backup and HTTPS commands.

## Implemented

- Base Compose preserves the legacy namespace/volumes and defaults to no live
  collection. Backend containers run non-root with read-only filesystems, tmpfs,
  reduced privileges, restart policies and bounded memory/CPU/PIDs/logs.
- Both workers have targeted health checks. Beat reports scheduler progress via
  a heartbeat. Warm shutdown windows protect in-flight work. Health failures
  still need monitoring; Docker restart policies do not act on unhealthy alone.
- Ollama is independent of ingestion startup. Full-stack web/worker settings
  share one provider configuration, fixing a mismatch that rejected queued model
  jobs. Generated Docker environments allow 180 seconds / 2048 output tokens;
  native settings are preserved. Automatic model prose is a separate opt-in.
- Optional Caddy overlay provides HTTPS, secure cookies and one trusted proxy
  peer. Explicit, distinct proxy/web addresses avoid an observed allocation
  collision. Only proxy ports are public. NVIDIA support is optional/config-only.
- Redis atomically shares API/admin account quotas across processes, including
  IP and account limits. Backend outage fails closed. Keys contain HMAC values;
  proxy headers from untrusted peers are ignored. Framing is denied. These
  address AUD-004 and AUD-011 within the supported single-edge/single-Redis setup.
- New environment helper refuses overwrites and nonignored output paths. Native
  transfer and Docker backup/restore helpers require quiet writers and an empty
  restore target; verify checksums, data, schema and sequence state; and never
  delete/clean a target. Backup retention and off-host storage remain operations.

## Executed verification

| Check | Result |
| --- | --- |
| Full isolated PostgreSQL suite | 624 tests passed, no skips; test database removed |
| Final helper/runtime checks | 10 environment/runtime tests and 26 recovery tests passed after final helper refinements |
| Compose configurations | Four synthetic base/full/override/HTTPS+GPU combinations passed |
| Image | Built successfully; UID 10001; no .env, artifacts, next-app, Git, Node/npm or persisted uv cache |
| Native to Linux transfer | 51 tables, 18,891 rows, 49 sequences, 198 indexes, 188 constraints matched |
| Restored HTTP workflows | 81 checks, including 47 static assets, CSRF/account permissions and graph save/reload/conflict/remove |
| Native collection guard | Real queued task returned disabled; no source collection was enabled |
| HTTPS and restart/outage | 15 checks; local CA chain validated; secure cookies; session/layout persisted through web/DB/Redis restart; Redis outage returned account 503 |
| Browser through HTTPS | Overview, Companies, People, Groups and English Swagger loaded; desktop/mobile overflow absent; no page exception |
| Shared quota concurrency | Two processes accepted 6+4, next attempt blocked after process restart; six processes/48 attempts accepted exactly 10; TTL and opaque keys checked |
| Docker backup recovery | Second independent project restored 51 tables/18,902 rows and all schema/sequence fingerprints; test accounts/views explain additional rows |
| Full stack and local model | All long-running services healthy, migrations/model initialisation exited successfully |
| Synthetic model job | Real Redis → AI-worker → Qwen3:4b → saved explanation succeeded in 101.655 s, 635 input/150 output tokens, one attempt; repeated request reused result |
| Preservation | All 51 working-table fingerprints, schema/sequence state and 31 protected file hashes unchanged |

The model test used CPU allocation without the GPU overlay. Existing weights
were copied to an independent model volume, then the normal initialisation pull
completed. This verifies reuse/initialisation, not a fresh weight download or
target-server latency. One small synthetic case does not establish model quality,
large-input performance or semantic correctness. All preexisting copied company,
graph, analysis, explanation and job/state rows remained unchanged in the probe.

Django deployment checks on the HTTPS profile reported only security.W004:
HSTS deliberately awaits the actual domain/HTTPS check. Public ACME issuance,
DNS/firewall policy, NVIDIA execution, load testing, unattended recovery and
off-host backup retention remain unverified. AUD-002 (novel model prose),
AUD-010 (dependency advisories), other audit findings and publication policy are
still gates for public launch. Resource/log bounds address the Docker portion
of AUD-017; this does not certify native log retention or eliminate monitoring.

Private reports are in artifacts/deploy-linux/ and artifacts/deployment/.
Both owned Compose projects and their test volumes/networks were removed after
verification. Native PostgreSQL/Redis and the native model cache were preserved;
no native process was started/stopped by this follow-up. Final Status reported
native worker and AI-worker running, beat stopped, with the last saved collection
cycle still dated 9 October. Do not infer active scheduling from idle workers.
No Git commands, paid inference, working migrations
or new source collection were performed.

## Single-file Compose follow-up, 10 October 2026

The later user-authorised repository cleanup consolidated the four Compose files
into docker-compose.yml with optional CPU/GPU/HTTPS profiles. The historical
results above used overlays; current commands are in DEPLOY.md. HTTPS retains a
loopback diagnostic web binding and validates the matching secure-cookie/trust
configuration. AI-worker startup checks local model metadata before consuming
jobs; ingestion remains independent. See REPOSITORY_AUDIT.md for new regression
and runtime checks. Existing namespace, volumes and recovery behavior remain.
