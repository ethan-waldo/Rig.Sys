"""Translator for Lips motion modules."""

from __future__ import annotations

from typing import Any, Dict

from rigsys.translation.modules.generic import GenericTranslator


class LipsTranslator(GenericTranslator):
    """Translator for rigsys Lips modules."""

    module_type = "Lips"

    def build_controls(self, module: Any, proxy_lookup: Dict[str, Any]):
        controls = super().build_controls(module, proxy_lookup)
        for control in controls:
            proxy_name = control.driven_proxy or ""
            if "Corner" in proxy_name:
                control.role = "lip_corner"
            elif "Up" in proxy_name:
                control.role = "lip_upper"
            elif "Lo" in proxy_name:
                control.role = "lip_lower"
            elif proxy_name == "Mouth":
                control.role = "lip_center"
        return controls

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        settings.update(
            {
                "lip_segments": getattr(module, "lipSegments", None),
                "number_of_joints": getattr(module, "numberOfJoints", None),
                "jaw_target": getattr(module, "jawTarget", None),
            }
        )
        return settings

