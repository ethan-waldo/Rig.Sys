"""Translator for Maya Limb motion module."""

from ..workflow_core import run_module_pipeline, translated_result


def translate(control_rig_bp, module_payload, shared):
    """Translate Limb module payload."""
    run_module_pipeline(control_rig_bp, module_payload, shared)
    return translated_result()
