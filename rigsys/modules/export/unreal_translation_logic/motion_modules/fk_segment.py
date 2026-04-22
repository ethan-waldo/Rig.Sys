"""Translator for Maya motion module FKSegment (FKRail)."""

from ..workflow_core import run_module_steps, translated_result


def translate(control_rig_bp, module_payload, shared):
    """Translate FKSegment module payload."""
    run_module_steps(control_rig_bp, module_payload, shared)
    return translated_result()
