"""Translator for Maya motion.Floating module."""

from .. import workflow_core


def translate(control_rig_bp, module_payload, shared):
    """Translate Floating module payload with explicit module-step flow."""
    notes = []
    logger = shared.get("log_warning")
    note = "Floating has no implemented Maya build path; custom RigUnit node required."
    notes.append(note)
    if callable(logger):
        logger(f"[Rig.Sys][Module:{module_payload.get('module_name')}] {note}")

    workflow_core.apply_module_steps(control_rig_bp, module_payload, shared)
    return {"status": "custom_node_required", "notes": notes}
