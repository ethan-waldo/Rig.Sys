"""Utility module translation helpers for generated Unreal scripts."""

from . import workflow_core


def apply_utility_module(control_rig_bp, module_payload, shared):
    """Apply utility module payload and emit custom-node requirements."""
    module_name = workflow_core.module_name(module_payload)
    module_type = module_payload.get("module_type", "")
    workflow_core.log_module_step(module_name, f"utility translator dispatch ({module_type})")

    unsupported_notes = {
        "ImportModel": "External mesh import must run through Unreal import task/custom node adapter.",
        "ControlShapeOverride": "Control shape CV transfer requires custom node/shape library bridge.",
        "PythonCode": "Arbitrary Python file execution should be exposed via a guarded custom node.",
    }

    if module_type in unsupported_notes:
        workflow_core.record_custom_node_requirement(module_payload, unsupported_notes[module_type], shared)

    return workflow_core.apply_module_payload(control_rig_bp, module_payload, shared)
