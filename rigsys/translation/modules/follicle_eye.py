"""Translator for FollicleEye motion modules."""

from __future__ import annotations

from typing import Any, Dict

from rigsys.translation.modules.generic import GenericTranslator


class FollicleEyeTranslator(GenericTranslator):
    """Translator for rigsys FollicleEye modules."""

    module_type = "FollicleEye"

    def build_controls(self, module: Any, proxy_lookup: Dict[str, Any]):
        controls = super().build_controls(module, proxy_lookup)
        for control in controls:
            proxy_name = control.driven_proxy or ""
            if proxy_name in ["In", "Out"]:
                control.role = "lid_corner"
            elif proxy_name.startswith("Up"):
                control.role = "lid_upper"
            elif proxy_name.startswith("Lo"):
                control.role = "lid_lower"
            elif proxy_name == "Eyeball":
                control.role = "eye_center"
        return controls

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        follicle_mesh = getattr(module, "follicleMesh", None)
        follicle_surface = getattr(module, "follicleSurface", None)
        if not follicle_mesh and not follicle_surface:
            self._last_warnings.append(
                "FollicleEye has no follicleMesh/follicleSurface set; lid attachment targets must be configured in Unreal."
            )
        settings.update(
            {
                "lid_segments": getattr(module, "lidSegments", None),
                "number_of_joints": getattr(module, "numberOfJoints", None),
                "follicle_mesh": follicle_mesh,
                "follicle_surface": follicle_surface,
                "eyeball": bool(getattr(module, "eyeball", False)),
            }
        )
        return settings
