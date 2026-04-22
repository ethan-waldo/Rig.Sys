"""Translator for utility.ControlShapeOverride module."""

from ..workflow_core import run_module_translation


def translate(control_rig_bp, module_payload, shared):
    """Translate ControlShapeOverride utility payload."""
    _ = control_rig_bp
    return run_module_translation(module_payload, shared)
