"""Motion module translation helpers for generated Unreal scripts."""

from .workflow_core import module_name


_SUPPORTED_MOTION_MODULES = {
    "Root",
    "FK",
    "FKSegment",
    "Limb",
    "QuadLimb",
    "Hand",
    "RibbonBindIK",
    "PointTarget",
    "FollicleEye",
    "Lips",
    "TestMotionModule",
}


def _module_requires_custom_node(module_payload):
    """Return custom-node warning text for known unsupported module cases."""
    module_type = module_payload.get("module_type")
    settings = module_payload.get("settings", {}) or {}
    if module_type in {"IK", "Floating"}:
        return f"{module_type} has no implemented Maya build path; custom RigUnit node required."
    if module_type == "Lips":
        return "Lips zipper/remap behavior is complex; custom RigUnit node may be required for exact parity."
    if module_type == "FollicleEye":
        return "FollicleEye mesh/follicle solve may require custom RigUnit node for deterministic parity."
    if module_type in {"Limb", "QuadLimb"} and settings.get("ikCtrlToFloor"):
        return "ikCtrlToFloor behavior may require custom RigUnit node for exact floor solve parity."
    if module_type == "RibbonBindIK" and settings.get("spans", 0) > 10:
        return "High-span RibbonBindIK may require custom RigUnit node for performance parity."
    return None


def apply_motion_module(control_rig_bp, module_payload, shared):
    """Apply one motion module payload via single-path per-module translation."""
    module_type = module_payload.get("module_type")
    name = module_name(module_payload)
    logger = shared.get("log_warning")
    if module_type not in _SUPPORTED_MOTION_MODULES:
        if callable(logger):
            logger(f"[Rig.Sys][Module:{name}] Unsupported motion module type '{module_type}'.")
        return {"status": "unsupported", "notes": [f"unsupported motion module type: {module_type}"]}

    custom_node_note = _module_requires_custom_node(module_payload)
    notes = []
    if custom_node_note:
        notes.append(custom_node_note)
        if callable(logger):
            logger(f"[Rig.Sys][Module:{name}] {custom_node_note}")

    shared.apply_module_payload(control_rig_bp, module_payload)
    status = "custom_node_required" if custom_node_note else "translated"
    return {"status": status, "notes": notes}
