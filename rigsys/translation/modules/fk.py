"""Translator for FK modules."""

from __future__ import annotations

from typing import Any, Dict

from rigsys.translation.modules.generic import GenericTranslator


class FKTranslator(GenericTranslator):
    """Translator for rigsys FK motion modules."""

    module_type = "FK"

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        settings.update(
            {
                "segments": getattr(module, "segments", None),
                "add_offsets": bool(getattr(module, "addOffsets", False)),
            }
        )
        return settings
