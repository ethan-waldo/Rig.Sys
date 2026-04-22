"""Translator for FKSegment motion modules."""

from __future__ import annotations

from typing import Any, Dict

from rigsys.translation.modules.generic import GenericTranslator


class FKSegmentTranslator(GenericTranslator):
    """Translate FKSegment modules."""

    module_type = "FKSegment"

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        settings.update(
            {
                "segments": getattr(module, "segments", None),
                "reverse": bool(getattr(module, "reverse", False)),
                "ik_rail": bool(getattr(module, "IKRail", False)),
                "add_offset": bool(getattr(module, "addOffset", False)),
            }
        )
        return settings
