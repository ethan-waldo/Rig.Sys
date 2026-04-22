"""Export module translation helpers for generated Unreal scripts."""

from .workflow_core import apply_module_payload


def apply_export_module(control_rig_bp, module_payload, shared):
    """Apply export module payload through shared per-module path."""
    return apply_module_payload(control_rig_bp, module_payload, shared)
