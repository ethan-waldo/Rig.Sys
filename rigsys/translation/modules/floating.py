"""Translator for Floating motion modules."""

from __future__ import annotations

from typing import Any, Dict, List

from rigsys.translation.models import ControlDefinition
from rigsys.translation.modules.generic import GenericTranslator


class FloatingTranslator(GenericTranslator):
    """Translator for rigsys floating modules."""

    module_type = "Floating"

    def build_controls(self, module: Any, proxy_lookup: Dict[str, Any]) -> List[ControlDefinition]:
        self._last_warnings.append("Floating module has no concrete buildModule implementation in rigsys.")
        controls = super().build_controls(module, proxy_lookup)
        for control in controls:
            control.role = "floating"
        return controls
