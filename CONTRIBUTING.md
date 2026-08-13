# Contributing to OIHK Basic

OIHK Basic welcomes focused fixes, tests, documentation, and product-polish improvements. The project is alpha software: a contribution should make current behavior more reliable or understandable without claiming unsupported readiness.

## Before opening a change

1. Check the issue tracker and [Known Limitations](docs/KNOWN_LIMITATIONS.md).
2. For a security issue, use a private GitHub security advisory instead of a public issue.
3. Keep real investigation data, credentials, model prompts, database files, logs, and build artifacts out of the repository.
4. Prefer a small branch with one purpose and tests close to the behavior it changes.

## Local setup

Follow the [Quick start](README.md#quick-start). Use Python 3.11 and Node 22; desktop work also requires Rust and the platform's Tauri dependencies.

## Required checks

Run the checks relevant to your change before opening a pull request. For a cross-cutting change, run the complete set in [Quality gates](README.md#quality-gates).

At minimum:

```powershell
python -m ruff check backend/app backend/run.py scripts tests --config backend/pyproject.toml
python -m pytest backend/tests tests --quiet --tb=short --no-header

cd frontend
npm run check
npm test
npm run build
```

Rust, packaging, dependency-audit, and platform-specific changes must also run the corresponding checks from [Building](docs/BUILDING.md).

## Pull requests

- Explain the user-visible problem and the chosen scope.
- List exact validation commands and results.
- Include screenshots for visual changes, captured with the [screenshot checklist](docs/screenshots/README.md).
- Call out security, privacy, migration, packaging, and data-integrity implications.
- Document known residual risks rather than hiding them behind broad claims.
- Do not include generated dependencies, local databases, evidence files, secrets, or unsigned installers.

Maintainers may ask for the change to be split when review or rollback would otherwise be difficult.
