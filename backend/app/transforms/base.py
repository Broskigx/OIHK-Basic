"""Transform base definition for OIHK Basic."""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class TransformSpec:
    id: str
    title: str
    description: str
    input_types: list[str]
    output_types: list[str]
    category: str
    cost: str = "free"
    requires: list[str] = field(default_factory=list)
    keyless: bool = True
    enabled: bool = True
    handler: Callable | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "input_types": self.input_types,
            "output_types": self.output_types,
            "category": self.category,
            "cost": self.cost,
            "requires": self.requires,
            "keyless": self.keyless,
            "enabled": self.enabled,
        }
