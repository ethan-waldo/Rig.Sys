"""Translator for Hand motion modules."""

from __future__ import annotations

from typing import Any, Dict, List

from rigsys.translation.models import ControlDefinition
from rigsys.translation.modules.generic import GenericTranslator


class HandTranslator(GenericTranslator):
    """Hand-specific translation rules."""

    module_type = "Hand"

    def build_controls(self, module: Any, proxy_lookup: Dict[str, Any]) -> List[ControlDefinition]:
        if getattr(module, "addOffset", False):
            self._last_warnings.append(
                "Hand addOffset behavior is exported as metadata; additional offset controls are not expanded."
            )
        controls = super().build_controls(module, proxy_lookup)
        for control in controls:
            proxy_name = control.driven_proxy or ""
            if proxy_name.startswith("Finger"):
                control.role = "finger"
            elif proxy_name.startswith("Thumb"):
                control.role = "thumb"
            elif proxy_name == "Global":
                control.role = "hand_global"
            elif proxy_name == "Root":
                control.role = "hand_root"
        return controls

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        settings.update(
            {
                "thumb": bool(getattr(module, "thumb", False)),
                "meta": bool(getattr(module, "meta", False)),
                "number_of_fingers": getattr(module, "numOfFingers", None),
                "number_of_finger_joints": getattr(module, "numOfFingerJoints", None),
                "number_of_thumb_joints": getattr(module, "numOfThumbJoints", None),
            }
        )
        return settings
