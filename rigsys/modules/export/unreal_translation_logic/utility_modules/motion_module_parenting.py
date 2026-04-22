"""Translator for Maya MotionModuleParenting utility module."""

from ..workflow_core import build_module_manifest, translated_result


def translate(control_rig_bp, module_payload, shared):
    """Translate MotionModuleParenting payload with explicit utility steps."""
    module_manifest = build_module_manifest(module_payload)
    shared.apply_constraints(control_rig_bp, module_manifest)
    shared.apply_rigvm_instructions(control_rig_bp, module_manifest)
    return translated_result()
