"""Translator for visibilityAttributeOverride utility module."""

from .. import workflow_core


def translate(control_rig_bp, module_payload, shared):
    """Translate VisibilityOverride utility module payload."""
    workflow_core.run_module_steps(control_rig_bp, module_payload, shared)
    return workflow_core.translated_result()
