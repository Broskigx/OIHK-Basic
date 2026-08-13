# Screenshot capture checklist

Product screenshots in this repository must be reproducible evidence of the current UI, not mockups.

## Capture environment

1. Build from the commit being documented and record its SHA.
2. Use a new disposable profile and synthetic investigation names. Never use real case data, evidence, people, credentials, endpoints, paths, or model conversations.
3. Use the default light theme, a 1440 × 900 viewport, and 100% display scaling unless a screenshot documents a responsive state.
4. Hide browser chrome when it is not relevant. Capture the Tauri shell for desktop-specific behavior.
5. Verify that visible counters, statuses, timestamps, model states, and errors came from the running application.

## Required set

| File | State to capture |
| --- | --- |
| `01-onboarding.png` | New profile, first onboarding step, before any runtime is configured. |
| `02-dashboard-empty.png` | Dashboard immediately after skipped onboarding with a genuinely empty database. |
| `03-investigation-graph.png` | One synthetic investigation with a small, deliberately created graph and no real identifiers. |
| `04-local-models.png` | Local Models showing honest status labels. If no runtime is running, capture the actionable empty state rather than fabricating a connection. |

## Review before committing

- The screenshot matches the current commit and has no placeholder overlays.
- No private data, secret, local username, absolute path, token, or identifiable host is visible.
- Empty/error states are real and their recovery action is readable.
- The image is cropped consistently and readable in the GitHub README width.
- The pull request states the platform, capture method, and whether a local model runtime was available.

Add only the smallest useful set. When a UI change makes an image stale, replace or remove it in the same pull request.
