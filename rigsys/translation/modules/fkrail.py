"""Translator for FKSegment motion modules."""

from __future__ import annotations

from typing import Any, Dict

from rigsys.translation.modules.generic import GenericTranslator


class FKSegmentTranslator(GenericTranslator):
    """Translate FKSegment modules."""

    module_type = "FKSegment"

    def build_metadata(self, module: Any) -> Dict[str, Any]:
        metadata = super().build_metadata(module)
        metadata["segment_count"] = len(getattr(module, "proxies", {}))
        return metadata
