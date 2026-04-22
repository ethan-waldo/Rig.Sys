"""Unreal translator for Maya IK motion module."""

from ..workflow_core import (
    apply_module_connections,
    apply_module_constraints,
    apply_module_controls,
    apply_module_custom_attributes,
    apply_module_ik_fk_systems,
    apply_module_joints,
    apply_module_rig_logic,
    apply_module_rigvm,
    translated_result,
)


def translate(control_rig_bp, module_payload, shared):
    """Translate IK module payload with explicit per-step execution."""
    apply_module_joints(control_rig_bp, module_payload, shared)
    apply_module_controls(control_rig_bp, module_payload, shared)
    apply_module_custom_attributes(control_rig_bp, module_payload, shared)
    apply_module_constraints(control_rig_bp, module_payload, shared)
    apply_module_ik_fk_systems(control_rig_bp, module_payload, shared)
    apply_module_rig_logic(control_rig_bp, module_payload, shared)
    apply_module_rigvm(control_rig_bp, module_payload, shared)
    apply_module_connections(control_rig_bp, module_payload, shared)
    return translated_result()
