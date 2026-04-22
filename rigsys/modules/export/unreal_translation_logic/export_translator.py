"""Export module translation helpers for generated Unreal scripts."""


def apply_export_module(control_rig_bp, module_payload, shared):
    """Apply export module payload through shared per-module path."""
    return shared.apply_module_payload(control_rig_bp, module_payload)
