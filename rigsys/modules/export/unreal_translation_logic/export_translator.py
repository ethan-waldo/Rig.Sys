"""Export module translation helpers for generated Unreal scripts."""

from . import workflow_core


def apply_export_module(control_rig_bp, module_payload, shared):
    """Apply export module payload with explicit, readable steps."""
    return workflow_core.translate_module_payload(control_rig_bp, module_payload, shared)
