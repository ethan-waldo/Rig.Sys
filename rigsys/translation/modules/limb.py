"""Limb motion module translator."""

from __future__ import annotations

from typing import Any, Dict, List

from rigsys.translation.models import ControlDefinition
from rigsys.translation.modules.generic import GenericTranslator


class LimbTranslator(GenericTranslator):
    """Translate limb modules with limb-specific metadata."""

    module_type = "Limb"

    def build_controls(self, module: Any, proxy_lookup: Dict[str, Any]) -> List[ControlDefinition]:
        controls: List[ControlDefinition] = []
        root_proxy = proxy_lookup.get(getattr(module, "nameSet", {}).get("Root", "Root"))
        if bool(getattr(module, "clavicle", False)) and root_proxy is not None:
            controls.append(
                ControlDefinition(
                    name=f"{module.getFullName()}_Clavicle_CTRL",
                    shape=str(getattr(module, "ctrlShapes", "circle")),
                    scale=list(getattr(module, "ctrlScale", [1.0, 1.0, 1.0])),
                    role="clavicle",
                    position=list(getattr(root_proxy, "position", [0.0, 0.0, 0.0])),
                    rotation=list(getattr(root_proxy, "rotation", [0.0, 0.0, 0.0])),
                    driven_proxy=getattr(root_proxy, "name", "Root"),
                )
            )

        controls.extend(super().build_controls(module, proxy_lookup))

        for control in controls:
            if control.role == "fk":
                control.role = "limb_fk"

        end_proxy_name = getattr(module, "nameSet", {}).get("End")
        for control in controls:
            if end_proxy_name and control.driven_proxy == end_proxy_name:
                control.role = "ik_effector"
                control.name = f"{module.getFullName()}_IK_CTRL"

        return controls

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        settings.update(
            {
                "number_of_joints": getattr(module, "numberOfJoints", None),
                "name_set": getattr(module, "nameSet", None),
                "pv_multiplier": getattr(module, "pvMultiplier", None),
                "ik_ctrl_to_floor": bool(getattr(module, "ikCtrlToFloor", False)),
                "foot": bool(getattr(module, "foot", False)),
                "clavicle": bool(getattr(module, "clavicle", False)),
            }
        )
        return settings
