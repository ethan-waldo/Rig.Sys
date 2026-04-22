"""SpaceSwitch utility module translator."""

from ..workflow_core import (
    apply_common_module_steps,
    custom_node_required_result,
    module_name,
    translated_result,
)


def translate(control_rig_bp, module_payload, shared):
    """Translate SpaceSwitch utility module payload."""
    notes = []
    settings = module_payload.get("settings", {}) or {}
    targets = settings.get("switchTargets") or []
    if len(targets) > 2:
        notes.append("Multi-target SpaceSwitch may need custom RigUnit for exact weighted blending UI parity.")

    apply_common_module_steps(control_rig_bp, module_payload, shared)
    if notes:
        logger = shared.get("log_warning")
        if callable(logger):
            logger(f"[Rig.Sys][Module:{module_name(module_payload)}] {notes[0]}")
        return custom_node_required_result(notes)
    return translated_result([])
