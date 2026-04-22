"""1:1 translator for Maya utility module RGBCurveColor."""

from ..workflow_core import apply_module_translation_steps, translated_result


def translate(control_rig_bp, module_payload, shared):
    """Apply RGBCurveColor module payload through explicit step orchestration."""
    apply_module_translation_steps(control_rig_bp, module_payload, shared)
    return translated_result()
