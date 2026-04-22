"""Translator for utility.ImportModel module."""

from ..workflow_core import apply_module_steps, custom_node_required


def translate(control_rig_bp, module_payload, shared):
    """Translate ImportModel utility module."""
    apply_module_steps(control_rig_bp, module_payload, shared)
    return custom_node_required(
        "ImportModel relies on external file import behavior and should be backed by Unreal import tooling."
    )
