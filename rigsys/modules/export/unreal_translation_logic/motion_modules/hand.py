"""Translator for Maya Hand motion module."""

from .. import workflow_core


def translate(control_rig_bp, module_payload, shared):
    """Translate Hand module payload."""
    workflow_core.apply_module_payload(control_rig_bp, module_payload, shared)
    return workflow_core.translated_result()
