"""Limb motion module translator."""

from __future__ import annotations

from typing import Any, Dict

from rigsys.translation.modules.generic import GenericTranslator


class LimbTranslator(GenericTranslator):
    """Translate limb modules with limb-specific metadata."""

    module_type = "Limb"

    def build_metadata(self, module: Any) -> Dict[str, Any]:
        metadata = super().build_metadata(module)
        metadata.update(
            {
                "number_of_joints": getattr(module, "numberOfJoints", None),
                "name_set": getattr(module, "nameSet", None),
                "pv_multiplier": getattr(module, "pvMultiplier", None),
                "ctrl_shapes": getattr(module, "ctrlShapes", None),
            }
        )
        return metadata
