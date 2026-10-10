# IZ2 web interface

This directory contains the React/TypeScript workspace. Django serves its built
assets at `/app/`; this is a Vite application, not a Next.js application.

## Source layout

| Directory | Responsibility |
| --- | --- |
| `src/pages/` | Route screens and their page-specific styles |
| `src/components/` | Shared interface, session and graph components |
| `src/components/design/` | Reusable surface and evidence presentation |
| `src/components/effects/` | Active decorative backgrounds and border effects |
| `src/components/motion/` | Accessible text, count and navigation motion |
| `src/lib/` | API boundary, shared domain types and formatting helpers |
| `src/i18n/` | EN/RU interface messages and persistent language preference |
| `src/styles/` | Global styles in the explicit cascade order in `main.tsx` |
| `src/test/` | Shared test environment; feature tests live beside their source |
| `public/` | Favicon and distributed third-party notices |
| `licenses/` | Full component licenses and source attribution |

Keep page/component styles beside their owners. The global styles are separate
layers of the accepted interface: preserve their import order when editing them.
Do not copy built bundles into `src/` or commit build outputs.

`../templates/` and `../static/` also serve the standalone English API reference
and retained `/legacy/` routes. They are active compatibility interfaces, not
duplicates of this workspace. Font/component licenses remain required even when
no runtime code imports the notice files.

## Local commands

Run these from `frontend/` with Node 22.12 or newer. On Windows PowerShell, use
`npm.cmd` if the execution policy prevents running `npm.ps1`.

```sh
npm ci
npm run dev
npm test -- --maxWorkers=2
npm run build
npm run format:check
```

The development server proxies `/api` to Django on `127.0.0.1:8000`. Production
builds go to the ignored `../static/frontend/` directory, including the Vite
manifest. Docker builds this output before Django collects static assets.
For native Django, collect static assets and restart the server after a build.

TypeScript checks unused local declarations and parameters as part of the build.
The tests use mocked API responses; they do not start parsers, model generation
or write to the working database. Source data and saved explanations retain their
original language when the interface language changes.
