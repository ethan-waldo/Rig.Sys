"""Translator for Maya Lips motion module."""

from .. import workflow_core


def translate(control_rig_bp, module_payload, shared):
    """Translate Lips payload through explicit module stages."""
    module_name = workflow_core.module_name(module_payload)
    workflow_core.log_module_step(module_name, "lips: apply custom attrs")
    shared["apply_custom_attributes"](control_rig_bp, module_payload)
    workflow_core.log_module_step(module_name, "lips: apply constraints")
    shared["apply_constraints"](control_rig_bp, module_payload)
    workflow_core.log_module_step(module_name, "lips: apply rig logic")
    shared["apply_rig_logic_nodes"](control_rig_bp, module_payload)
    workflow_core.log_module_step(module_name, "lips: apply rigvm")
    shared["apply_rigvm"](control_rig_bp, module_payload)
    return workflow_core.translator_result("translated")
