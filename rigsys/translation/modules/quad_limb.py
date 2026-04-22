"""Translator for QuadLimb motion modules."""

from __future__ import annotations

from typing import Any, Dict

from rigsys.translation.modules.limb import LimbTranslator


class QuadLimbTranslator(LimbTranslator):
    """QuadLimb shares limb translation behavior."""

    module_type = "QuadLimb"

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        settings.update(
            {
                "curved_calf": bool(getattr(module, "curvedCalf", False)),
            }
        )
        return settings

