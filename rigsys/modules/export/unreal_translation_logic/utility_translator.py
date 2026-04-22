"""Utility module translation helpers for generated Unreal scripts."""


def apply_utility_module(control_rig_bp, module_payload, shared):
    """Apply one utility module through shared module payload path."""
    return shared.apply_module_payload(control_rig_bp, module_payload)
