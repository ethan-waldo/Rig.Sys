"""Translator for RibbonBindIK motion modules."""

from __future__ import annotations

from typing import Any, Dict, List

from rigsys.translation.models import ControlDefinition
from rigsys.translation.modules.generic import GenericTranslator


class RibbonBindIKTranslator(GenericTranslator):
    """Translator for rigsys RibbonBindIK modules."""

    module_type = "RibbonBindIK"

    def build_controls(self, module: Any, proxy_lookup: Dict[str, Any]) -> List[ControlDefinition]:
        if getattr(module, "meta", False):
            self._last_warnings.append(
                "RibbonBindIK meta ribbon layering is exported as settings metadata; Control Rig graph nodes are not auto-generated."
            )
        controls = super().build_controls(module, proxy_lookup)
        for control in controls:
            control.role = "ribbon"
        return controls

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        settings.update(
            {
                "spans": getattr(module, "spans", None),
                "reverse": bool(getattr(module, "reverse", False)),
                "meta": bool(getattr(module, "meta", False)),
                "number_of_joints": getattr(module, "numberOfJoints", None),
            }
        )
        return settings
