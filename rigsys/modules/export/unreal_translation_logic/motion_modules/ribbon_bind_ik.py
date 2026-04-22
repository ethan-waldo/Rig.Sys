"""Translator for Maya RibbonBindIK motion module."""

from ..workflow_core import apply_module_payload, translated_result


def translate(control_rig_bp, module_payload, shared):
    """Translate RibbonBindIK module payload."""
    apply_module_payload(control_rig_bp, module_payload, shared)
    # RibbonBindIK is expected to map to spline/curve style rig units in Unreal.
    return translated_result()
