"""Translator for Maya QuadLimb motion module."""

from .. import workflow_core


def translate(control_rig_bp, module_payload, shared):
    """Translate QuadLimb module payload."""
    notes = []
    settings = module_payload.get("settings", {}) or {}
    if settings.get("ikCtrlToFloor"):
        notes.append("ikCtrlToFloor requires floor-projected solve node to match Maya behavior.")

    workflow_core.execute_module_steps(control_rig_bp, module_payload, shared)
    return workflow_core.result_from_notes(notes)
