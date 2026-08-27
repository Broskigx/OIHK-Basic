"""Presentational catalog of OIHK modules Basic knows how to talk about.

This exists so the control plane can show a module that is *not installed yet*
— its name, what it is for, and the fact that installing it is an option —
rather than an empty list that tells the operator nothing.

It is presentation only, and that distinction matters. An earlier version of
this file was a host *adapter* that pairing consulted as a gate: it pinned one
module id, one product name and one entrypoint, and refused everything else as
``module_not_first_party``. That made "System Link links separately installed
OIHK modules" true of precisely one module, and it added no security worth the
cost — a package's trustworthiness is established by
:mod:`app.system_link.publisher_trust`, which verifies a publisher signature
over the package content against embedded trust anchors. Anyone able to forge
that signature could equally well write "OIHK Evidence Lab Basic" into a
manifest, so the name check only ever excluded honest modules.

Adding an entry here advertises a module. It grants nothing, trusts nothing,
and is not consulted during pairing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    """One module Basic will advertise before it is installed."""

    module_id: str
    product_name: str
    summary: str


KNOWN_MODULES: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        module_id="oihk.evidence-lab",
        product_name="OIHK Evidence Lab",
        summary=(
            "Forensic acquisition, hashing, carving and analysis. Installed separately and linked "
            "through System Link; Basic renders its surface and holds the custody chain."
        ),
    ),
)
