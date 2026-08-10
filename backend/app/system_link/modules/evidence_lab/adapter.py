"""Basic-side identity and lifecycle constraints for the separate Evidence Lab product."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceLabHostAdapter:
    module_id: str = "oihk.evidence-lab"
    product_name: str = "OIHK Evidence Lab Basic"
    lifecycle_entrypoint_id: str = "evidence-lab-runtime"

    def validate_identity(self, *, module_id: str, product_name: str, entrypoint_id: str) -> None:
        if module_id != self.module_id:
            raise ValueError("Module id is not in the Basic first-party System Link catalog")
        if product_name != self.product_name:
            raise ValueError("Evidence Lab product identity does not match the host catalog")
        if entrypoint_id != self.lifecycle_entrypoint_id:
            raise ValueError("Evidence Lab lifecycle identity does not match the host adapter")


EVIDENCE_LAB_ADAPTER = EvidenceLabHostAdapter()
