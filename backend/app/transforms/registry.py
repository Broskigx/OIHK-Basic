"""Transform registry for OIHK Basic."""

from typing import ClassVar

from app.transforms.base import TransformSpec
from app.transforms.catalog import BUILT_IN_TRANSFORMS


class TransformRegistry:
    _instance: ClassVar["TransformRegistry | None"] = None

    def __init__(self) -> None:
        self._specs: dict[str, TransformSpec] = {}
        for spec in BUILT_IN_TRANSFORMS:
            self._specs[spec.id] = spec

    @classmethod
    def get_instance(cls) -> "TransformRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, transform_id: str) -> TransformSpec | None:
        return self._specs.get(transform_id)

    def all(self) -> list[TransformSpec]:
        return list(self._specs.values())

    def for_input(self, input_type: str) -> list[TransformSpec]:
        return [s for s in self._specs.values() if input_type in s.input_types]

    def categories(self) -> list[str]:
        cats: list[str] = []
        seen: set[str] = set()
        for spec in self._specs.values():
            if spec.category not in seen:
                seen.add(spec.category)
                cats.append(spec.category)
        return cats


registry = TransformRegistry.get_instance()
