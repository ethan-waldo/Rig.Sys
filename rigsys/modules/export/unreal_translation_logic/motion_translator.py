"""Motion module translation helpers for generated Unreal scripts."""


def apply_motion_module(control_rig_bp, module_payload, shared):
    """Apply one motion module payload via shared generated-script callbacks."""
    return shared.apply_module_payload(control_rig_bp, module_payload)
