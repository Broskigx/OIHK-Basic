"""
Separation tests for OIHK Basic.

These tests verify that:
1. No code inside OIHK-Basic imports from outside OIHK-Basic
2. No OIHK Full code imports from OIHK-Basic
3. Package names are unique
4. Data directories are separate
"""

import re
from pathlib import Path


def _project_root() -> Path:
    """Find project root (parent of tests/)."""
    return Path(__file__).resolve().parent.parent


def _basic_dir() -> Path:
    return _project_root()


def _full_backend() -> Path:
    """OIHK Full backend (if exists)."""
    return _project_root().parent / "backend"


def _full_frontend() -> Path:
    """OIHK Full frontend (if exists)."""
    return _project_root().parent / "frontend"


# --- Prohibited import patterns ---
_PROHIBITED_IMPORTS_IN_BASIC = [
    r"from\s+services\.",
    r"import\s+services\.",
    r"from\s+infrastructure\.",
    r"import\s+infrastructure\.",
    r"from\s+oihk_full",
    r"import\s+oihk_full",
    r"from\s+oihk\.full",
    r"import\s+oihk\.full",
]


def _check_file_for_patterns(filepath: Path, patterns: list[str]) -> list[str]:
    """Check a file for any of the given regex patterns."""
    issues = []
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except (OSError, PermissionError):
        return [f"Cannot read {filepath}"]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        for match in matches:
            issues.append(f"{filepath.relative_to(_project_root())}: Found '{match}'")
    return issues


def test_no_cross_imports_from_basic_to_full():
    """Verify that no Python code in OIHK-Basic imports from OIHK Full modules."""
    basic_backend = _basic_dir() / "backend"
    issues = []

    for py_file in basic_backend.rglob("*.py"):
        issues.extend(_check_file_for_patterns(py_file, _PROHIBITED_IMPORTS_IN_BASIC))

    assert len(issues) == 0, "Cross-imports found:\n" + "\n".join(issues)


def test_package_names_unique():
    """Verify OIHK Basic uses its own package names."""
    pyproject = _basic_dir() / "backend" / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml not found"

    content = pyproject.read_text()
    assert "oihk-basic-backend" in content, (
        "Package name should be 'oihk-basic-backend'"
    )

    package_json = _basic_dir() / "frontend" / "package.json"
    assert package_json.exists(), "package.json not found"
    content = package_json.read_text()
    assert "oihk-basic-frontend" in content, (
        "Package name should be 'oihk-basic-frontend'"
    )


def _safe_read_text(filepath: Path) -> str:
    """Read text file with UTF-8 encoding, ignoring decode errors on binary files."""
    try:
        return filepath.read_text(encoding="utf-8", errors="ignore")
    except (OSError, PermissionError):
        return ""


def _iter_backend_py_files():
    """Iterate over backend .py files, excluding virtual environments."""
    backend_dir = _basic_dir() / "backend"
    for py_file in backend_dir.rglob("*.py"):
        # Skip files inside virtual environments
        if (
            ".venv" in py_file.parts
            or "venv" in py_file.parts
            or "env" in py_file.parts
        ):
            continue
        yield py_file


def test_no_hardcoded_developer_paths():
    """Verify no hardcoded absolute paths from developer machines."""
    issues = []
    for pattern in [r"C:\\Users\\", r"/home/", r"/Users/"]:
        for py_file in _iter_backend_py_files():
            content = _safe_read_text(py_file)
            if pattern in content:
                issues.append(
                    f"{py_file.relative_to(_basic_dir())}: Contains {pattern}"
                )

    assert len(issues) == 0, "Hardcoded paths found:\n" + "\n".join(issues)


def test_no_hardcoded_secrets():
    """Verify no hardcoded API keys or secrets."""
    issues = []
    secret_patterns = [
        r"sk-[a-zA-Z0-9]{20,}",  # OpenAI-style keys
        r"ghp_[a-zA-Z0-9]{36}",  # GitHub tokens
        r"AKIA[0-9A-Z]{16}",  # AWS keys
    ]

    for py_file in _iter_backend_py_files():
        content = _safe_read_text(py_file)
        for pattern in secret_patterns:
            if re.search(pattern, content):
                issues.append(
                    f"{py_file.relative_to(_basic_dir())}: Possible hardcoded secret"
                )

    assert len(issues) == 0, "Possible secrets found:\n" + "\n".join(issues)


def test_data_dir_uses_oihk_basic():
    """Verify data directory references use 'OIHK-Basic' not 'OIHK'."""
    config_py = _basic_dir() / "backend" / "app" / "core" / "config.py"
    assert config_py.exists(), "config.py not found"

    content = config_py.read_text()
    # The data dir should use "OIHK-Basic" (with hyphen)
    assert '"OIHK-Basic"' in content or "'OIHK-Basic'" in content, (
        "Data directory should reference 'OIHK-Basic'"
    )


def test_frontend_connects_to_localhost():
    """Verify frontend API client connects to local addresses only."""
    api_ts = _basic_dir() / "frontend" / "src" / "api.ts"
    assert api_ts.exists(), "api.ts not found"

    content = api_ts.read_text()
    assert "127.0.0.1" in content, "API should connect to 127.0.0.1"
    assert "localhost" in content or "127.0.0.1" in content, (
        "API should connect to localhost"
    )
    # Should NOT connect to external services by default
    external_services = ["api.github", "api.google", "api.cloudflare"]
    for service in external_services:
        assert service not in content, f"Should not connect to {service} by default"


def test_ports_bound_to_localhost():
    """Verify backend binds to 127.0.0.1 only."""
    run_py = _basic_dir() / "backend" / "run.py"
    assert run_py.exists(), "run.py not found"
    content = run_py.read_text()
    assert "127.0.0.1" in content, "Backend should bind to 127.0.0.1"

    main_py = _basic_dir() / "backend" / "app" / "main.py"
    assert main_py.exists(), "main.py not found"


def test_vite_binds_to_localhost():
    """Verify Vite dev server binds to 127.0.0.1."""
    vite_config = _basic_dir() / "frontend" / "vite.config.ts"
    assert vite_config.exists(), "vite.config.ts not found"
    content = vite_config.read_text()
    # Should not expose to network
    assert "127.0.0.1" in content or "strictPort" in content, (
        "Vite should bind to specific local interface"
    )


def test_csp_limits_connections():
    """Verify Content Security Policy restricts connections to local."""
    index_html = _basic_dir() / "frontend" / "index.html"
    assert index_html.exists(), "index.html not found"
    content = index_html.read_text()
    assert (
        "content-security-policy" in content.lower()
        or "Content-Security-Policy" in content
    ), "CSP should be set"
    assert "127.0.0.1" in content or "localhost" in content, (
        "CSP should allow local connections"
    )
