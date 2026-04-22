"""Maya-side translation pipeline from rigsys modules to Control Rig data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

from rigsys.translation.models import RigDefinition, RigModuleDefinition
from rigsys.translation.registry import translate_motion_module

logger = logging.getLogger(__name__)


def translate_motion_modules(rig) -> List[RigModuleDefinition]:
    """Translate all motion modules in build order."""
    ordered_modules = sorted(
        rig.motionModules.values(),
        key=lambda module: module.buildOrder,
    )
    # Ensure mirrored modules generated in preBuild are also included in the export payload.
    if hasattr(rig, "preBuild"):
        try:
            rig.preBuild()
            ordered_modules = sorted(
                rig.motionModules.values(),
                key=lambda module: module.buildOrder,
            )
        except Exception as exc:
            # Translation should remain best-effort even when preBuild side effects fail.
            logger.warning("Rig preBuild failed during translation export: %s", exc)
    return [translate_motion_module(module) for module in ordered_modules]


def build_rig_definition(rig) -> RigDefinition:
    """Build a serializable rig definition for Unreal."""
    return RigDefinition(
        rig_name=rig.name,
        modules=translate_motion_modules(rig),
    )


def build_rig_definition_payload(rig) -> Dict:
    """Return dict payload to write as JSON."""
    return build_rig_definition(rig).to_dict()


def export_rig_definition_to_json(rig, output_path: str) -> str:
    """Export a rig definition JSON payload from a rigsys rig instance."""
    payload = build_rig_definition_payload(rig)
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=4), encoding="utf-8")
    return str(output)
