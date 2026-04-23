"""Translator for PointTarget motion modules."""

from __future__ import annotations

from typing import Any, Dict, List

from rigsys.translation.models import ControlDefinition
from rigsys.translation.modules.generic import GenericTranslator


class PointTargetTranslator(GenericTranslator):
    """Translator for rigsys PointTarget modules."""

    module_type = "PointTarget"

    def build_controls(self, module: Any, proxy_lookup: Dict[str, Any]) -> List[ControlDefinition]:
        controls = super().build_controls(module, proxy_lookup)
        for control in controls:
            control.role = "point_target"
        return controls

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        targets = getattr(module, "targets", [])
        if isinstance(targets, str):
            targets = [targets]
        influences = list(getattr(module, "targetsInfluence", []) or [])
        targets = list(targets or [])
        if targets and influences and len(targets) != len(influences):
            self._last_warnings.append(
                f"PointTarget targetsInfluence length mismatch: {len(influences)} influences for {len(targets)} targets."
            )
        settings.update(
            {
                "targets": targets,
                "constrain_type": getattr(module, "constrainType", None),
                "effect_targets": bool(getattr(module, "effectTargets", False)),
                "maintain_offset": bool(getattr(module, "maintainOffset", True)),
                "targets_influence": influences,
            }
        )
        return settings
