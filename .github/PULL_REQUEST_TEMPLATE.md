<!--
Keep a pull request to one theme. If this branch grew several, split it so a
reviewer can read one commit and understand one decision.
Security vulnerabilities go in a private advisory, not here.
-->

## What changed, and why it was wrong

<!--
The why is the part that matters. State the defect, what it actually cost, and
what the failure looked like — not a restatement of the diff.
-->

## How it was verified

<!--
Name the test that fails without this change. If there is none, say why the
change is not testable rather than leaving the question open.
For a fix: confirm you broke the code and watched the test go red.
For a performance change: the measurement, before and after, and how you took it.
-->

## Checks

- [ ] `python -m ruff check backend/app backend/run.py backend/tests scripts tests`
- [ ] `python -m pytest backend/tests tests -q`
- [ ] `cd frontend && npm run lint && npm test && npm run build`
- [ ] `cd src-tauri && cargo fmt -- --check && cargo check --locked && cargo test --locked --all-targets`

<!-- Only the ones your change can affect. `npm run build` is not optional if you touched TypeScript: it runs the type check without an incremental cache. -->

## Review notes

- [ ] Comments explain why, and every claim in them is true of the code as merged
- [ ] No documentation now describes a control that does not exist (`THREAT_MODEL.md`, `SECURITY.md`, `docs/KNOWN_LIMITATIONS.md`)
- [ ] Anything touching authorization, evidence, custody or the network boundary fails closed
- [ ] No new runtime dependency, or it is justified in the description
- [ ] No open release gate is described as done (clean-VM install, signed updater, macOS/Linux artifacts)
- [ ] No real investigation data, secrets or evidence files in the diff, the tests or the description
