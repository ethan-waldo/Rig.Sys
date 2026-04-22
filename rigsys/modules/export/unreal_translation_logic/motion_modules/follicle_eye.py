"""FollicleEye motion module translator."""

from .. import workflow_core


def translate(control_rig_bp, module_payload, shared):
    """Translate FollicleEye module payload with explicit pipeline steps."""
    workflow_core.run_module_custom_attributes(control_rig_bp, module_payload, shared)
    workflow_core.run_module_constraints(control_rig_bp, module_payload, shared)
    workflow_core.run_module_ik_fk_systems(control_rig_bp, module_payload, shared)
    workflow_core.run_module_rig_logic(control_rig_bp, module_payload, shared)
    workflow_core.run_module_rigvm(control_rig_bp, module_payload, shared)
    return {
        "status": "translated",
        "notes": [],
    }
