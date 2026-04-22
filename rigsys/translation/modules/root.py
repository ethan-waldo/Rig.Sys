"""Translator for Root motion modules."""

from __future__ import annotations

from typing import Any, List

from rigsys.translation.models import ControlDefinition
from rigsys.translation.modules.base import ModuleTranslator


class RootTranslator(ModuleTranslator):
    """Root-specific translation with optional offset control."""

    module_type = "Root"

    def build_controls(self, module: Any) -> List[ControlDefinition]:
        controls = [
            ControlDefinition(
                name=f"{module.getFullName()}_CTRL",
                shape=str(getattr(module, "ctrlShapes", "circle")),
                scale=list(getattr(module, "ctrlScale", [1.0, 1.0, 1.0])),
                role="root",
            )
        ]

        if getattr(module, "addOffset", False):
            base_scale = list(getattr(module, "ctrlScale", [1.0, 1.0, 1.0]))
            controls.append(
                ControlDefinition(
                    name=f"{module.getFullName()}Offset_CTRL",
                    shape=str(getattr(module, "ctrlShapes", "circle")),
                    scale=[axis * 0.75 for axis in base_scale],
                    role="offset",
                    parent_control=f"{module.getFullName()}_CTRL",
                )
            )
        return controls
