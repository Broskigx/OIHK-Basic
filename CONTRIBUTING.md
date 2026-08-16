# Contributing to OIHK Basic

OIHK Basic is a local-first investigation platform. It handles evidence, chain
of custody and authorization boundaries, which changes what "done" means here:
a change is finished when it is correct, when the reasoning behind it survives
in the file, and when a test would notice if someone undid it.

This document is written in English, like the rest of the engineering
documentation (`SECURITY.md`, `THREAT_MODEL.md`, `docs/`). The README is the
Spanish-language front door for the product itself. Code, comments and tests
are English.

## Before you start

- Security vulnerabilities do **not** go in an issue. Open a private GitHub
  security advisory, as described in [SECURITY.md](SECURITY.md). Never attach
  real investigation data, secrets or evidence files to anything public.
- The project is `0.2.0-beta.1`. Three release gates are open and depend on
  hardware and secrets rather than code: installation on a clean Windows VM,
  the signed updater against a controlled HTTPS endpoint, and the macOS and
  Linux artifacts. Do not describe any of them as done in code, comments,
  documentation or a pull request.
- Read [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). Several
  "missing" behaviours are deliberate product boundaries, and a pull request
  that removes one is a product decision, not a bug fix.

## Environment

Requirements: Git, Python 3.11 or newer, Node.js 22 (`>=22 <23`), stable Rust
with Cargo, and the native Tauri 2 dependencies for your platform (see
[docs/BUILDING.md](docs/BUILDING.md)).

```bash
git clone https://github.com/Broskigx/OIHK-Basic.git
cd OIHK-Basic

cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

cd ../frontend
npm ci
```

Running the app is covered in the README: backend via `python run.py`,
frontend via `npm run dev`, and the desktop shell via `npm run desktop:dev`
with Vite already running.

## The checks that gate a pull request

These are the same commands CI runs. Run them from the repository root before
opening a pull request; running them locally is much faster than discovering a
failure in Actions.

```bash
python -m ruff check backend/app backend/run.py backend/tests scripts tests
python -m pytest backend/tests tests -q
python scripts/version.py check
```

```bash
cd frontend
npm run lint
npm test
npm run build
npm audit --audit-level=high
```

```bash
cd src-tauri
cargo fmt -- --check
cargo check --locked
cargo test --locked --all-targets
```

`npm run check` runs the type check and ESLint together, but it is **not** a
substitute for `npm run build`. The build is the step that runs the full type
check without an incremental cache standing in for it, and it has caught type
errors that `npm run check` did not.

Coverage runs inside the test step in CI, with a floor of 70%:

```bash
python -m pytest backend/tests tests -q --cov=app --cov-report=term-missing
```

That floor is a regression guard against a whole route silently losing its
tests. It is not a target to chase, and padding it with tests that execute
lines without pinning behaviour makes the signal worse.

Optional, and the same checks in the same configuration:

```bash
python -m pip install pre-commit
pre-commit install
```

`.pre-commit-config.yaml` deliberately runs nothing CI does not. A hook that
disagrees with the pipeline is worse than no hook — it teaches you to bypass
it.

## Two configuration details that are load-bearing

Both look like noise and are not. Removing either produces a build that still
passes while reporting something untrue.

- **`concurrency = ["greenlet", "thread"]`** under `[tool.coverage.run]` in
  `backend/pyproject.toml`. SQLAlchemy's asyncio layer switches greenlets, and
  without declaring that, the tracer loses the frame after every
  `await session.execute(...)` and reports the following line as unexecuted.
  Declaring it moved the case router from a reported 38% to 91% without a
  single test changing.
- **`ruff.toml` at the repository root**, which extends
  `backend/pyproject.toml`. Without it, a run from the root loses
  `known-first-party` and reports import-order errors that CI considers clean.

## Standards

### Comments explain why

A comment states why the code is the way it is and what breaks otherwise —
never what the code literally does. If a control is subtle, say what it does
*not* cover, so nobody infers more from it than it delivers.

Read `backend/app/middleware/origin_guard.py` for the reference. It explains
why an `Origin` check cannot address DNS rebinding and why the `Host` check
exists separately, which is the kind of reasoning that stops the next person
from deleting one of them as redundant.

The inverse rule matters just as much: **a comment that describes a control
which is not in the code is a defect**, and a worse one than a missing
comment, because it is read as an assurance. The same applies to
`THREAT_MODEL.md`.

### A test must fail against the bug it describes

Before you keep a test, break the code it covers and confirm it goes red, then
restore. A test that passes with and without the behaviour costs runtime and
buys false confidence.

This is a real filter, not a slogan. A test asserting that an oversized
request answers `413` also passes against an implementation that reads the
whole file into memory before rejecting it — so the test that actually pins
the bounded read counts the bytes pulled off disk instead.

Backend integration tests go over real HTTP through the full middleware stack,
using the shared fixtures in `backend/tests/conftest.py`: each gets its own
SQLite database with `foreign_keys=ON`, and only the session factory and the
authenticated identity are substituted. Do not build a parallel harness. That
distinction is not academic — running this way is what surfaced a case
deletion failure that no direct function call could reproduce, because the
constraint that refused it was never enabled.

The frontend has no testing library; component tests use `createRoot` and
`act` directly, with `vi.mock` at the boundaries. See
`frontend/src/app/useInterfaceMotion.test.tsx`.

### Fail closed

When a check cannot reach a decision, refuse. Deriving a permissive default
from missing configuration is how a guard silently stops guarding. If you add
an entry to a registry that another registry has to mirror, make the missing
half refuse rather than allow.

## Commits and pull requests

Commits follow `type(scope): subject` — `fix(cases): …`, `security(api): …`,
`test(access): …`, `docs: …`, `build: …`, `refactor: …`, `feat(ui): …`.

The subject says what changed. **The body says why it was wrong**, in prose,
including what the failure actually was and what it cost. Read `git log` for
the standard. A body that restates the diff adds nothing; a body that explains
the defect is what makes the history worth reading in a year.

Keep a pull request to one theme. If a branch grew several, split it into
commits that each stand alone — a reviewer should be able to read one commit
and understand one decision.

### What a reviewer will check

- Does the change do what the commit message says, and nothing else?
- Is there a test that fails without the fix?
- Do the comments explain the reasoning, and is every claim in them true?
- Does any documentation now describe a control that no longer exists?
- For anything touching authorization, evidence, custody or the network
  boundary: what is the failure mode, and does it fail closed?
- Are new dependencies justified? This is a local-first security tool; every
  package added to the desktop bundle is supply-chain surface.

## Reporting a bug

Use the issue templates. Include the version from `VERSION`, your operating
system, and what you expected against what happened. Sanitize logs before
attaching them — diagnostics can contain paths and case metadata.
