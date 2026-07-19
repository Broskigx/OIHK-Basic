# OIHK Basic

**Local-first investigation and OSINT platform.**

> Subido por **Broskigx** — Edición comunitaria de OIHK con funciones limitadas pero completamente funcional.

OIHK Basic es una edición ligera y respetuosa con la privacidad de la plataforma OIHK. Se ejecuta completamente de forma local — sin servicios cloud, sin telemetría, sin dependencias externas.

## Features

- **Case Management** — Create and manage local investigations with full legal scoping
- **Source Ingestion** — Add text and URL sources to your cases
- **Target Profiles** — Create target profiles with photos and aliases
- **Intelligence Graph** — Visualize entities and relationships in a graph database
- **Graph Analytics** — Network analysis with hubs, components, and degree metrics
- **Entity Management** — Browse, search, and manage all entities in your cases
- **Evidence Vault** — Track sealed evidence with tamper-evident chain of custody
- **OSINT Enrichment** — Free public lookups (DNS, RDAP/WHOIS, crt.sh)
- **Forensic Analysis** — File hashing, MIME detection, metadata extraction, IOC scanning
- **Data Carving** — Extract embedded files (PNG, JPEG, ZIP) from binary data
- **Interesting Files** — Declarative rules to flag files of interest
- **Hash Sets** — Import known-file hashes for matching (notable/known-good)
- **Cross-Case Correlation** — Find overlaps between investigations
- **Transforms** — One-click entity enrichment (DNS, WHOIS, certificate search)
- **Machines** — Deterministic transform chains
- **Reports** — Generate markdown investigation reports
- **Timeline** — Chronological view of case activity
- **Data Export** — Export cases as JSON for backup
- **Graph Import/Export** — CSV and GraphML formats
- **Local Authentication** — User accounts with PBKDF2 password hashing
- **CSRF Protection** — Double-submit cookie pattern
- **Rate Limiting** — In-process sliding window rate limiter

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React + Vite)            │
│  Port 5173 (127.0.0.1 only)                         │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (JSON)
                       ▼
┌─────────────────────────────────────────────────────┐
│              Backend (FastAPI + Uvicorn)              │
│  Port 8000 (127.0.0.1 only)                         │
├─────────────────────────────────────────────────────┤
│  SQLAlchemy ORM → SQLite (local file)                │
│  Local file storage (./storage/)                     │
│  In-process rate limiter (no Redis)                  │
└─────────────────────────────────────────────────────┘
```

**Key design decisions:**
- All data stored locally in SQLite
- No Redis, no cloud services, no telemetry
- Authentication via local JWT tokens
- File storage on local filesystem
- No MCP servers, no licensing system, no enterprise features

## Prerequisites

- Python 3.11 or later
- Node.js 18 or later (for frontend development)
- pip (Python package manager)

## Quick Start

### 1. Backend Setup

```bash
# Navigate to the backend directory
cd OIHK-Basic/backend

# Create a virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -e .

# Copy and configure environment
cp ../.env.example .env
# Edit .env if needed (defaults work for development)

# Start the server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup

```bash
# Open a new terminal
cd OIHK-Basic/frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

### 3. Access the Application

- **Frontend:** http://127.0.0.1:5173
- **API Docs:** http://127.0.0.1:8000/docs
- **API:** http://127.0.0.1:8000

### 4. First-Run Setup

On first run, the application will:
1. Create the SQLite database file (`oihk-basic.db`)
2. Create the storage directory (`./storage/`)
3. Create all database tables

To create an admin account, either:
- Set `OIHK_BOOTSTRAP_ADMIN_EMAIL` and `OIHK_BOOTSTRAP_ADMIN_PASSWORD` in `.env`
- Or register via the UI (if `OIHK_PUBLIC_REGISTRATION=true`)

## Environment Variables

Copy `.env.example` to `.env` and configure as needed. All variables are optional.

| Variable | Default | Description |
|----------|---------|-------------|
| `OIHK_APP_NAME` | OIHK Basic | Application name |
| `OIHK_ENVIRONMENT` | development | Runtime environment |
| `OIHK_DATABASE_URL` | sqlite+aiosqlite:///./oihk-basic.db | Database connection |
| `OIHK_CORS_ORIGINS` | http://127.0.0.1:5173,... | Allowed CORS origins |
| `OIHK_STORAGE_DIR` | ./storage | Local file storage path |
| `OIHK_JWT_SECRET` | (default) | JWT signing key |
| `OIHK_CUSTODY_SIGNING_KEY` | (default) | Evidence signing key |
| `OIHK_AUTH_ENABLED` | true | Enable authentication |
| `OIHK_BOOTSTRAP_ADMIN_EMAIL` | — | First admin email |
| `OIHK_BOOTSTRAP_ADMIN_PASSWORD` | — | First admin password |
| `OIHK_PUBLIC_REGISTRATION` | true in dev | Enable self-registration |
| `OIHK_SEARXNG_URL` | — | Self-hosted SearXNG instance |
| `OIHK_BRAVE_API_KEY` | — | Brave Search API key |
| `OIHK_AI_BASE_URL` | — | Local/cloud AI endpoint |
| `OIHK_AI_API_KEY` | — | AI provider API key |
| `OIHK_AI_MODEL` | — | AI model name |
| `OIHK_AI_LOCAL` | false | Keyless local AI server |

## Development

### Backend

```bash
cd OIHK-Basic/backend
pip install -e ".[dev]"
ruff check .
pytest
```

### Frontend

```bash
cd OIHK-Basic/frontend
npm run dev     # Development server
npm run build   # Production build
npm run lint    # Lint
npm test        # Run tests
```

## Build for Production

### Backend

```bash
cd OIHK-Basic/backend
pip install -e .
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd OIHK-Basic/frontend
npm run build
# Serve the dist/ directory with any static file server
```

## Security

- All ports bind to `127.0.0.1` only (not exposed to the network)
- CSRF protection via double-submit cookie pattern
- Rate limiting on all API endpoints
- Passwords hashed with PBKDF2-HMAC-SHA256
- JWTs with HS256 signing
- Input validation on all API endpoints
- File path sanitization to prevent path traversal
- Content Security Policy in HTML template
- No telemetry, no external data transmission

## Data Storage

All data is stored locally:

| Data | Location |
|------|----------|
| Database | `./oihk-basic.db` (configurable via `OIHK_DATABASE_URL`) |
| Uploaded files | `./storage/` (configurable via `OIHK_STORAGE_DIR`) |
| Configuration | `.env` file in project root |

To change the storage location, use absolute paths in the `.env` file:
```
OIHK_DATABASE_URL=sqlite+aiosqlite:////home/user/.oihk-basic/data.db
OIHK_STORAGE_DIR=/home/user/.oihk-basic/storage
```

## What's Different from Full OIHK

| Feature | OIHK (Full) | OIHK Basic |
|---------|-------------|------------|
| MCP Servers | ✓ | ✗ Removed |
| AI Assistant | ✓ | ✗ Removed |
| Licensing System | ✓ | ✗ Removed |
| Enterprise Features | ✓ | ✗ Removed |
| Cloud Infrastructure | ✓ | ✗ Removed |
| Redis Cache | ✓ | ✗ Removed |
| GraphQL API | ✓ | ✗ Removed |
| Desktop (Tauri) | ✓ | ✗ Removed |
| Update System | ✓ | ✗ Removed |
| Billing | ✓ | ✗ Removed |
| Streaming Events | ✓ | ✗ Removed |
| Policy Service | Full | Simplified |
| Data Portability | Full | JSON Export |
| Authentication | Cloud-ready | Local JWT Only |
| File Storage | Configurable | Local Filesystem |
| Web Search | Multiple providers | Simplified |

## Créditos

**Publicado por:** Broskigx

Esta edición OIHK Basic fue preparada y distribuida por Broskigx como una versión comunitaria de OIHK, con funciones limitadas para ejecución local.

## License

OIHK Basic is distributed under the MIT License. See the [LICENSE](./LICENSE) file for details.

## Acknowledgments

Built on open-source technologies: FastAPI, SQLAlchemy, React, Vite, and more.

OIHK Basic is a community edition derived from the OIHK platform.
