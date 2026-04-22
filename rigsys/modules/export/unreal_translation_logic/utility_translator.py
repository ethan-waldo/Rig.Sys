"""Utility module translation helpers for generated Unreal scripts."""

from . import workflow_core
from .utility_modules import (
    bind_joints,
    control_shape_override,
    curve_color,
    import_model,
    motion_module_parenting,
    python_code,
    space_switch,
    visibility_override,
)


_UTILITY_TRANSLATORS = {
    "BindJoints": bind_joints.translate,
    "MotionModuleParenting": motion_module_parenting.translate,
    "SpaceSwitch": space_switch.translate,
    "ImportModel": import_model.translate,
    "RGBCurveColor": curve_color.translate,
    "ControlShapeOverride": control_shape_override.translate,
    "VisibilityOverride": visibility_override.translate,
    "PythonCode": python_code.translate,
}


def apply_utility_module(control_rig_bp, module_payload, shared):
    """Apply utility module payload through dedicated per-module translators."""
    module_name = workflow_core.module_name(module_payload)
    module_type = module_payload.get("module_type", "")
    workflow_core.log_module_step(shared, module_name, f"utility translator dispatch ({module_type})")

    translator = _UTILITY_TRANSLATORS.get(module_type)
    if translator is None:
        workflow_core.record_unsupported_module_result(
            module_payload,
            f"Unsupported utility module type '{module_type}'.",
            shared,
        )
        return {"status": "unsupported", "notes": [f"unsupported utility module type: {module_type}"]}

    return translator(control_rig_bp, module_payload, shared)
