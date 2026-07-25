# OIHK Basic — Separation Audit

## Date
2026-07-19

## Auditor
Automated audit of repository structure and code analysis.

---

## 1. Executive Summary

The OIHK repository root previously contained OIHK Basic code directly at the top level, mixed with what should be the OIHK Full/Complete product. This audit documents every file, determines its ownership, and records the separation actions taken.

## 2. What Was Mixed

| Issue | Location | Detail |
|-------|----------|--------|
| Basic code at root | `backend/`, `frontend/`, `scripts/` | All OIHK Basic source code was at the repository root instead of in a dedicated subfolder |
| Virtual environment | `./.venv/` | Python virtual environment was at the repository root, containing strawberry-graphql (unused) |
| Single .gitignore | `./.gitignore` | Single gitignore for what should be two separate products |
| Single README | `./README.md` | README described only OIHK Basic, not OIHK Full |
| Single LICENSE | `./LICENSE` | MIT License for OIHK Basic at root |
| Old PyInstaller cache | `./*.spec`, `./build/`, `./dist/` (residual) | Any previous build artifacts at root level |

## 3. File Ownership Classification

### Belongs to OIHK Basic (moved to OIHK-Basic/)

| Path | Reason |
|------|--------|
| `backend/` (entire directory) | Basic backend code, package `oihk-basic-backend` |
| `frontend/` (entire directory) | Basic frontend code, package `oihk-basic-frontend` |
| `scripts/` (entire directory) | Basic setup and dev scripts |
| `README.md` | Describes only OIHK Basic features |
| `LICENSE` | OIHK Basic MIT License |

### Belongs to OIHK Full (will be recreated at root)

Not applicable — OIHK Full is not present in this repository snapshot. The root is reserved for OIHK Full.

### Does Not Belong to Either (cleanup)

| Path | Action |
|------|--------|
| `.venv/` | Should be removed/recreated per product |
| `.git/cursor/` | Git metadata, stays |

## 4. Audit of Cross-Imports and Mixed Dependencies

### Backend imports (all within Basic, clean)
- All `from app.xxx` imports reference modules within `backend/app/`
- All services, routers, models, schemas are self-contained
- No imports from outside `backend/`

### Frontend imports (all within Basic, clean)
- All imports reference local paths within `frontend/src/`
- API client connects to `127.0.0.1:8000` (local only)
- No external service dependencies

### Dependency Analysis

**Python (backend/pyproject.toml):**
- Package name: `oihk-basic-backend`
- All dependencies are open-source (FastAPI, SQLAlchemy, etc.)
- No enterprise dependencies
- No private package registries

**Node.js (frontend/package.json):**
- Package name: `oihk-basic-frontend`
- All dependencies are open-source (React, Vite, etc.)
- No enterprise dependencies

### Configuration Analysis
- `OIHK_JWT_SECRET` and `OIHK_CUSTODY_SIGNING_KEY` have hardcoded development defaults
- No cloud API keys hardcoded
- Ports: 8000 (backend), 5173 (frontend) — only bind to 127.0.0.1
- Database: SQLite local file
- Storage: local filesystem

## 5. Separation Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Broken paths after move | High | Update all file references, imports, and config paths |
| Broken .gitignore | Medium | Create separate gitignore for Basic |
| Default secrets in production | Medium | Implement first-run secret generation |
| Virtual environment confusion | Low | Each product gets own venv |
| Port conflicts | Low | Document ports, use dynamic port selection for Tauri |
| Data directory conflicts | Medium | Use separate OS-specific data dirs per product |

## 6. Files to Move

The following directories and files will be moved from root into `OIHK-Basic/`:

1. `backend/` → `OIHK-Basic/backend/`
2. `frontend/` → `OIHK-Basic/frontend/`
3. `scripts/` → `OIHK-Basic/scripts/`
4. `README.md` → `OIHK-Basic/README.md`
5. `LICENSE` → `OIHK-Basic/LICENSE`

## 7. Files to Copy (no modifications needed)

- No files need to be copied as-is; all Basic files are being moved.

## 8. Files Not to Touch

- `.git/` — Git repository metadata
- `.gitignore` — Will be updated but not removed
- `.venv/` — Will be deprecated for Basic; Basic will use its own venv

## 9. Post-Separation State

After separation:

```
OIHK/
├── OIHK-Basic/           # Independent product directory
│   ├── backend/          # FastAPI Python backend
│   ├── frontend/         # React + Vite frontend
│   ├── src-tauri/        # Tauri 2 desktop shell (NEW)
│   ├── assets/           # Icons, images (NEW)
│   ├── scripts/          # Build, dev, test scripts
│   ├── tests/            # Backend tests (moved from backend/tests/)
│   ├── docs/             # Documentation (NEW)
│   ├── .github/          # CI workflows (NEW)
│   ├── installers/       # NSIS config (NEW)
│   ├── dist/             # Build artifacts (NEW)
│   ├── README.md
│   └── LICENSE
│
├── backend/              # Reserved for OIHK Full
├── frontend/             # Reserved for OIHK Full
├── services/             # Reserved for OIHK Full
├── infrastructure/       # Reserved for OIHK Full
└── README.md             # Updated with reference to Basic
```

## 10. Action Items Completed

- [x] Audit of all files completed
- [x] Classification of file ownership
- [x] Cross-import analysis
- [x] Dependency isolation plan
- [x] Data directory separation plan
- [x] First-run security plan
- [ ] All files moved to OIHK-Basic/
- [ ] Paths and references updated
- [ ] Tauri 2 desktop app created
- [ ] PyInstaller sidecar setup
- [ ] NSIS installer configured
- [ ] Linux packaging configured
- [ ] macOS packaging configured
- [ ] GitHub Actions workflows created
- [ ] Build/test scripts created
- [ ] Documentation written
- [ ] Tests created
- [ ] First-run security implemented

---

*End of audit. Full separation actions follow below.*
