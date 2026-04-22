"""Motion module translation dispatcher."""

from .workflow_core import module_name
from .motion_modules import (
    fk,
    fk_segment,
    floating,
    follicle_eye,
    hand,
    ik,
    limb,
    lips,
    point_target,
    quad_limb,
    ribbon_bind_ik,
    root,
    test_motion_module,
)


MODULE_TRANSLATORS = {
    "Root": root.translate,
    "FK": fk.translate,
    "FKSegment": fk_segment.translate,
    "Limb": limb.translate,
    "QuadLimb": quad_limb.translate,
    "Hand": hand.translate,
    "RibbonBindIK": ribbon_bind_ik.translate,
    "PointTarget": point_target.translate,
    "FollicleEye": follicle_eye.translate,
    "Lips": lips.translate,
    "TestMotionModule": test_motion_module.translate,
    "IK": ik.translate,
    "Floating": floating.translate,
}


def apply_motion_module(control_rig_bp, module_payload, shared):
    """Apply one motion module payload via per-module translator file."""
    module_type = module_payload.get("module_type")
    translator = MODULE_TRANSLATORS.get(module_type)
    if translator is None:
        name = module_name(module_payload)
        logger = shared.get("log_warning")
        if callable(logger):
            logger(f"[Rig.Sys][Module:{name}] Unsupported motion module type '{module_type}'.")
        return {"status": "unsupported", "notes": [f"unsupported motion module type: {module_type}"]}
    return translator(control_rig_bp, module_payload, shared)
