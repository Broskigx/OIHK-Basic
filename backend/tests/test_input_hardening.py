"""Adversarial regressions for import, export, and limiter input boundaries."""

from __future__ import annotations

import json
import math

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.database import Base
from app.services.graph_io import import_entities_csv
from app.services.hash_intel import import_hash_entries

# The private helpers below are imported inside each test rather than at module
# scope on purpose: it keeps this file collectable against the pre-hardening
# tree, so the end-to-end cases can be run there to confirm they genuinely
# reproduce the defect instead of merely failing to import.


# --------------------------------------------------------------------------
# CSV import: confidence must be a finite number in [0, 1]
# --------------------------------------------------------------------------


@pytest.mark.parametrize("hostile", ["nan", "NaN", "inf", "-inf", "Infinity"])
def test_confidence_rejects_non_finite_values(hostile):
    """`min(float('nan'), 1.0)` returns NaN, which is not serialisable as JSON."""
    from app.services.graph_io import _parse_confidence

    with pytest.raises(ValueError):
        _parse_confidence(hostile)


def test_confidence_clamps_out_of_range_values():
    from app.services.graph_io import _parse_confidence

    assert _parse_confidence("-99999") == 0.0
    assert _parse_confidence("42") == 1.0
    assert _parse_confidence("") == pytest.approx(0.68)
    assert _parse_confidence("0.5") == 0.5


def test_nan_confidence_would_have_produced_invalid_json():
    """Documents the downstream impact the guard prevents."""
    assert math.isnan(min(float("nan"), 1.0))
    assert json.dumps({"confidence": float("nan")}) == '{"confidence": NaN}'
    with pytest.raises(ValueError):
        json.loads('{"confidence": NaN}', parse_constant=_reject)


def _reject(token):
    raise ValueError(f"invalid JSON constant: {token}")


@pytest.mark.asyncio
async def test_csv_import_rejects_nan_confidence_row(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'graph.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        case = models.Case(title="Import case", summary="s", legal_basis="court order", scope_statement="lawful scope statement")
        session.add(case)
        await session.flush()

        summary = await import_entities_csv(
            session,
            case_id=case.id,
            csv_text="label,type,confidence\nevil.test,domain,nan\ngood.test,domain,0.5\n",
        )
        await session.commit()

        assert summary.nodes == 1
        assert any("confidence" in error for error in summary.errors)
        stored = (await session.execute(models.Entity.__table__.select())).fetchall()
        assert all(math.isfinite(row.confidence) for row in stored)
    await engine.dispose()


@pytest.mark.asyncio
async def test_csv_import_stops_at_the_row_limit(tmp_path, monkeypatch):
    # Each accepted row costs an INSERT, a flush, and a custody seal, so the
    # ceiling is lowered here rather than importing 10,000 real rows.
    monkeypatch.setattr("app.services.graph_io._MAX_IMPORT_ROWS", 5)

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'graph-rows.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        case = models.Case(
            title="Bulk", summary="s", legal_basis="court order", scope_statement="lawful scope statement"
        )
        session.add(case)
        await session.flush()

        rows = "\n".join(f"host{index}.test,domain,0.5" for index in range(25))
        summary = await import_entities_csv(
            session,
            case_id=case.id,
            csv_text=f"label,type,confidence\n{rows}\n",
        )
        assert summary.nodes == 5
        assert any("row limit" in error for error in summary.errors)
    await engine.dispose()


# --------------------------------------------------------------------------
# Hash sets: digest length must agree with the algorithm
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hostile",
    ["abc123", "a" * 63, "a" * 65, "", "zz" * 16, "0123456789abcdef"],
)
def test_classify_digest_rejects_length_algorithm_mismatch(hostile):
    from app.services.hash_intel import _classify_digest

    assert _classify_digest(hostile) is None


def test_classify_digest_accepts_the_three_supported_lengths():
    from app.services.hash_intel import _classify_digest

    assert _classify_digest("0" * 32) == ("md5", "0" * 32)
    assert _classify_digest("A" * 40) == ("sha1", "a" * 40)  # case-normalised
    assert _classify_digest("  " + "F" * 64 + "  ") == ("sha256", "f" * 64)  # trimmed


@pytest.mark.asyncio
async def test_hash_import_counts_short_digests_as_invalid(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'hashes.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        summary = await import_hash_entries(
            session,
            organization_id="system",
            set_name="known-bad",
            category="malware",
            severity="high",
            text="deadbeef sample-too-short\n" + ("a" * 64) + " real-sha256\n",
        )
        await session.commit()
        assert summary.added == 1
        assert summary.invalid == 1
    await engine.dispose()


# --------------------------------------------------------------------------
# Export headers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hostile,expected_absent",
    [
        ('x" ; filename="evil.html', '"'),
        ("x\r\nX-Injected: 1", "\r"),
        ("x\nSet-Cookie: a=b", "\n"),
        ("../../etc/passwd", "/"),
    ],
)
def test_export_filename_token_strips_header_breaking_characters(hostile, expected_absent):
    from app.routers.exports import _safe_filename_token

    token = _safe_filename_token(hostile)
    assert expected_absent not in token
    assert all(character.isalnum() or character in "-_" for character in token)


def test_export_filename_token_never_empty():
    from app.routers.exports import _safe_filename_token

    assert _safe_filename_token("!!!") == "case"
    assert _safe_filename_token("") == "case"
