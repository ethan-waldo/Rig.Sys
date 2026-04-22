"""Translator for utility.PythonCode module."""

from ..workflow_core import apply_standard_module_steps, custom_node_required_result


def translate(control_rig_bp, module_payload, shared):
    """Translate PythonCode utility module payload."""
    apply_standard_module_steps(control_rig_bp, module_payload, shared)
    return custom_node_required_result(
        "PythonCode module execution requires guarded custom Unreal node/script bridge."
    )
