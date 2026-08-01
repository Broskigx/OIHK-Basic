# Responsible Use Policy

_Last updated: 2026-07-31 · Applies to OIHK Basic v0.1.x_

OIHK Basic is an open-source intelligence and digital forensics tool. It is
designed **exclusively for authorized investigations and lawful use**.

## 1. Authorized use only

- Use OIHK Basic only for investigations you are legally authorized to
  conduct: your own assets, assets of an organization that employs you for
  that purpose, or engagements covered by written authorization, warrants or
  equivalent legal authority.
- You are responsible for complying with the laws, regulations and ethical
  standards that apply in your jurisdiction, including data-protection and
  privacy legislation.
- OIHK Basic does **not** provide legal authority. Authorization is yours.

## 2. What you must not do

- Do not use OIHK Basic for harassment, stalking, doxxing, fraud, identity
  theft, unauthorized surveillance or any other unlawful purpose.
- Do not attempt to access systems, data or accounts you are not authorized
  to access.
- Do not use OSINT adapters to attack or abuse the services they query.
  Respect rate limits, terms of service and applicable law.

## 3. Local AI assistance

- The copilot runs against **local models** you control. Model output is
  generated locally and is **unverified**: verify every claim before acting
  on it.
- Generated text may contain errors or hallucinations. It must never be
  presented as evidence without independent verification, and it can never
  initiate actions on your behalf automatically.
- Sensitive actions always require explicit confirmation and clearly show
  what will be executed.

## 4. Evidence integrity

- Evidence uploads are hashed (SHA-256) and stored under managed storage so
  the chain can be verified.
- Do not alter, delete or fabricate evidence. Export and share investigation
  material only with people who are authorized to receive it.
- When you delete data, it is removed from the managed storage; coordinate
  deletions with any retention or legal-hold obligations that apply to you.

## 5. Privacy

- OIHK Basic is local-first and collects no telemetry. Still, be careful
  about the data you import: it may contain personal or sensitive
  information belonging to third parties. See [PRIVACY.md](PRIVACY.md).

## 6. Reporting concerns

If you believe OIHK Basic has a security vulnerability, report it through
the private advisory process described in [SECURITY.md](SECURITY.md). Do not
include real investigation data, secrets or evidence files in the report.
