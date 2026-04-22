"""Translator for Hand motion modules."""

from __future__ import annotations

from typing import Any, Dict

from rigsys.translation.modules.generic import GenericTranslator


class HandTranslator(GenericTranslator):
    """Hand-specific translation rules."""

    module_type = "Hand"

    def build_metadata(self, module: Any) -> Dict[str, Any]:
        metadata = super().build_metadata(module)
        metadata.update(
            {
                "fingers": getattr(module, "fingers", None),
                "thumb": getattr(module, "thumb", None),
                "meta": getattr(module, "meta", None),
            }
        )
        return metadata
